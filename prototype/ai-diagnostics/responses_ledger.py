"""Durable, content-free reservations for one AI gateway authorization scope.

Only RESERVED permits one upstream attempt. No request, result or key is stored.
Expired attempts become UNCERTAIN permanently; terminal UUID tombstones are never
recycled. Keep this private database and its stable HMAC key on durable storage.
Deleting/restoring the database or changing the key is an operator migration, not
an automatic recovery mechanism. A completed response cannot be replayed here.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
import hashlib
import hmac
import math
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import time
import uuid
from typing import Callable, Iterator


class LedgerError(RuntimeError):
    """Storage or scope continuity failed. Do not issue an upstream request."""


@dataclass(frozen=True)
class Reservation:
    request_id: str
    expires_at: int
    _owner: bytes = field(repr=False)


@dataclass(frozen=True)
class ReservationResult:
    status: str
    reservation: Reservation | None = None
    retry_after: int = 0


class Ledger:
    """Short SQLite transactions serialize reservations across threads/processes.

    First provisioning requires initialize=True explicitly. Normal startup must
    use the default False so a missing/empty database cannot reset paid history.
    fingerprint_key must be a stable, dedicated, >=32-byte server secret kept in
    memory/environment, never in this database. Scope mismatch fails closed.
    complete/uncertain return False for a stale/expired/already-terminal lease;
    storage failures raise LedgerError. Neither accepts response content.
    The concurrency bound counts live local leases, not remote requests that may
    survive a network timeout. Enforce an upstream deadline in the HTTP adapter.
    Canonical body bytes must cover actual model/provider/configuration as well
    as the submitted evidence; the ledger does not infer execution semantics.
    """
    def __init__(self, path: str | os.PathLike[str], fingerprint_key: bytes, *,
                 reservation_ttl: int = 120, rate_limit: int = 30,
                 rate_window_seconds: int = 60, max_inflight: int = 4,
                 max_records: int = 100_000, max_body_bytes: int = 1_048_576,
                 busy_timeout_seconds: float = 5.0,
                 clock: Callable[[], float] = time.time, initialize: bool = False):
        if not isinstance(fingerprint_key, bytes) or not 32 <= len(fingerprint_key) <= 4096:
            raise ValueError("A stable dedicated fingerprint key of 32..4096 bytes is required")
        limits = ((reservation_ttl, 86_400), (rate_limit, 1_000_000),
                  (rate_window_seconds, 86_400), (max_inflight, 10_000),
                  (max_records, 10_000_000), (max_body_bytes, 1_048_576))
        if any(type(value) is not int or not 1 <= value <= maximum for value, maximum in limits):
            raise ValueError("Invalid ledger bounds")
        if isinstance(busy_timeout_seconds, bool) or not isinstance(busy_timeout_seconds, (int, float)) or not 0 < busy_timeout_seconds <= 30:
            raise ValueError("Invalid ledger busy timeout")
        if type(initialize) is not bool:
            raise ValueError("initialize must be explicit boolean")
        self.path = Path(path).absolute()
        self._key = fingerprint_key
        self._binding = hmac.digest(fingerprint_key, b"pocketchat-ledger-scope-v1", "sha256")
        self.reservation_ttl = reservation_ttl
        self.rate_limit = rate_limit
        self.rate_window_seconds = rate_window_seconds
        self.max_inflight = max_inflight
        self.max_records = max_records
        self.max_body_bytes = max_body_bytes
        self.busy_timeout_seconds = busy_timeout_seconds
        self._clock = clock
        try:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            parent = self.path.parent.stat()
            if parent.st_uid != os.getuid() or parent.st_mode & 0o022:
                raise LedgerError("Ledger directory must be owned privately and not writable by other users")
            if initialize:
                try:
                    descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
                except FileExistsError:
                    pass
                else:
                    os.close(descriptor)
            self._check_files()
            with self._connect() as db:
                if db.execute("PRAGMA journal_mode=WAL").fetchone()[0].lower() != "wal":
                    raise LedgerError("Durable ledger mode unavailable")
                db.execute("BEGIN IMMEDIATE")
                if not initialize:
                    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if not {"metadata", "reservations"} <= tables:
                        raise LedgerError("Existing ledger schema is unavailable")
                db.execute("CREATE TABLE IF NOT EXISTS metadata (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL, binding BLOB NOT NULL, last_now INTEGER NOT NULL)")
                db.execute("CREATE TABLE IF NOT EXISTS reservations (request_id TEXT PRIMARY KEY, fingerprint BLOB NOT NULL CHECK(length(fingerprint)=32), state TEXT NOT NULL CHECK(state IN ('IN_PROGRESS','UNCERTAIN','COMPLETED')), reserved_at INTEGER NOT NULL, expires_at INTEGER NOT NULL, updated_at INTEGER NOT NULL, owner BLOB CHECK(owner IS NULL OR length(owner)=32))")
                db.execute("CREATE INDEX IF NOT EXISTS reservation_time ON reservations(reserved_at)")
                db.execute("CREATE INDEX IF NOT EXISTS reservation_state ON reservations(state, expires_at)")
                row = db.execute("SELECT version,binding FROM metadata WHERE singleton=1").fetchone()
                if row is None:
                    if not initialize:
                        raise LedgerError("Existing ledger continuity metadata is unavailable")
                    # A database containing records without continuity metadata is not new.
                    if db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0]:
                        raise LedgerError("Ledger continuity metadata is unavailable")
                    db.execute("INSERT INTO metadata VALUES(1,1,?,?)", (self._binding, self._raw_now()))
                elif row[0] != 1 or not hmac.compare_digest(row[1], self._binding):
                    raise LedgerError("Ledger scope or version does not match")
                db.commit()
            self._check_files()
            current = self.path.stat()
            self._file_identity = (current.st_dev, current.st_ino)
        except LedgerError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError) as error:
            raise LedgerError("Ledger initialization unavailable") from None

    def _check_files(self) -> None:
        for suffix in ("", "-wal", "-shm", "-journal"):
            candidate = Path(str(self.path) + suffix)
            try:
                info = candidate.lstat()
            except FileNotFoundError:
                if suffix:
                    continue
                raise LedgerError("Ledger file disappeared") from None
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise LedgerError("Ledger files must be private regular files")
            if not suffix and hasattr(self, "_file_identity") and self._file_identity != (info.st_dev, info.st_ino):
                raise LedgerError("Ledger file was replaced during this process")

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._check_files()
        db = None
        try:
            # mode=rw prevents a missing database from being silently recreated.
            db = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True,
                                 timeout=self.busy_timeout_seconds, isolation_level=None)
            db.execute("PRAGMA synchronous=FULL")
            db.execute("PRAGMA trusted_schema=OFF")
            db.execute("PRAGMA temp_store=MEMORY")
            yield db
        finally:
            if db is not None:
                db.close()

    def _raw_now(self) -> int:
        value = self._clock()
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value < 2**53:
            raise LedgerError("Ledger clock unavailable")
        return int(value)

    def _now(self, db: sqlite3.Connection) -> int:
        row = db.execute("SELECT version,binding,last_now FROM metadata WHERE singleton=1").fetchone()
        if row is None or row[0] != 1 or not hmac.compare_digest(row[1], self._binding):
            raise LedgerError("Ledger scope or continuity changed")
        now = max(self._raw_now(), row[2])
        db.execute("UPDATE metadata SET last_now=? WHERE singleton=1", (now,))
        return now

    @staticmethod
    def _expire(db: sqlite3.Connection, now: int) -> int:
        # Retain body fingerprint and UUID forever; only the expired lease is cleared.
        return db.execute("UPDATE reservations SET state='UNCERTAIN',owner=NULL,updated_at=? WHERE state='IN_PROGRESS' AND expires_at<=?", (now, now)).rowcount

    @staticmethod
    def _identifier(request_id: str) -> None:
        if not isinstance(request_id, str) or len(request_id) != 36:
            raise ValueError("Idempotency ID must be a canonical UUID")
        try:
            if str(uuid.UUID(request_id)) != request_id:
                raise ValueError()
        except (ValueError, AttributeError):
            raise ValueError("Idempotency ID must be a canonical UUID") from None

    def reserve(self, request_id: str, body: bytes) -> ReservationResult:
        self._identifier(request_id)
        if not isinstance(body, bytes) or not 1 <= len(body) <= self.max_body_bytes:
            raise ValueError("Request body is empty or exceeds the ledger limit")
        fingerprint = hmac.digest(self._key, b"pocketchat-ledger-body-v1\0" + body, "sha256")
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                now = self._now(db)
                self._expire(db, now)
                row = db.execute("SELECT fingerprint,state FROM reservations WHERE request_id=?", (request_id,)).fetchone()
                if row is not None:
                    result = ReservationResult(row[1] if hmac.compare_digest(row[0], fingerprint) else "CONFLICT")
                elif db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0] >= self.max_records:
                    result = ReservationResult("CAPACITY")
                else:
                    recent = db.execute("SELECT COUNT(*),MIN(reserved_at) FROM reservations WHERE reserved_at>?", (now - self.rate_window_seconds,)).fetchone()
                    running = db.execute("SELECT COUNT(*),MIN(expires_at) FROM reservations WHERE state='IN_PROGRESS'").fetchone()
                    if recent[0] >= self.rate_limit:
                        result = ReservationResult("RATE_LIMITED", retry_after=max(1, recent[1] + self.rate_window_seconds - now))
                    elif running[0] >= self.max_inflight:
                        result = ReservationResult("RATE_LIMITED", retry_after=max(1, running[1] - now))
                    else:
                        owner = secrets.token_bytes(32)
                        expiry = now + self.reservation_ttl
                        db.execute("INSERT INTO reservations VALUES(?,?,'IN_PROGRESS',?,?,?,?)", (request_id, fingerprint, now, expiry, now, hashlib.sha256(owner).digest()))
                        result = ReservationResult("RESERVED", Reservation(request_id, expiry, owner))
                db.commit()
                return result
        except LedgerError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError) as error:
            raise LedgerError("Ledger reservation unavailable; upstream request is not authorized") from None

    def _terminal(self, reservation: Reservation, state: str) -> bool:
        if not isinstance(reservation, Reservation) or not isinstance(reservation._owner, bytes) or len(reservation._owner) != 32:
            raise ValueError("A valid reservation lease is required")
        self._identifier(reservation.request_id)
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                now = self._now(db)
                self._expire(db, now)
                changed = db.execute("UPDATE reservations SET state=?,owner=NULL,updated_at=? WHERE request_id=? AND owner=? AND state='IN_PROGRESS' AND expires_at>?", (state, now, reservation.request_id, hashlib.sha256(reservation._owner).digest(), now)).rowcount
                db.commit()
                return changed == 1
        except LedgerError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError) as error:
            raise LedgerError("Ledger completion unavailable; the attempt remains uncertain") from None

    def complete(self, reservation: Reservation) -> bool:
        return self._terminal(reservation, "COMPLETED")

    def uncertain(self, reservation: Reservation) -> bool:
        return self._terminal(reservation, "UNCERTAIN")

    def sweep(self) -> int:
        """Expire leases without deleting UUID tombstones or permitting paid replays."""
        try:
            with self._connect() as db:
                db.execute("BEGIN IMMEDIATE")
                changed = self._expire(db, self._now(db))
                db.commit()
                return changed
        except LedgerError:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError) as error:
            raise LedgerError("Ledger expiry unavailable") from None
