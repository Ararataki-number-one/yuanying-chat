"""Offline persistence/concurrency/expiry tests; no network or upstream SDKs."""
from contextlib import contextmanager
import concurrent.futures
import dataclasses
import multiprocessing
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest
import uuid
from responses_ledger import Ledger, LedgerError, Reservation

KEY = b"synthetic-ledger-key-not-a-real-secret-00000001"
BODY = b'{"version":1,"provider":"openai","model":"fixture-model","evidence":[]}'

def reserve_process(path, request_id, body, ready, start, output):
    ledger = Ledger(path, KEY)
    ready.put(True); start.wait(5)
    output.put(ledger.reserve(request_id, body).status)

def crash_after_reserve(path, request_id, pipe):
    result = Ledger(path, KEY, clock=lambda: 1000).reserve(request_id, BODY)
    pipe.send(result.status); pipe.close(); os._exit(0)

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="responses-ledger-")
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "private" / "ledger.sqlite"
        self.now = 1000
    def make(self, *, initialize=True, key=KEY, **kwargs):
        return Ledger(self.path, key, clock=lambda: self.now, initialize=initialize, **kwargs)
    def request_id(self): return str(uuid.uuid4())
    def test_first_reservation_only_has_send_permission(self):
        ledger=self.make(); rid=self.request_id(); first=ledger.reserve(rid,BODY)
        self.assertEqual(first.status,"RESERVED"); self.assertIsInstance(first.reservation,Reservation)
        second=ledger.reserve(rid,BODY)
        self.assertEqual(second.status,"IN_PROGRESS"); self.assertIsNone(second.reservation)
        self.assertTrue(ledger.complete(first.reservation))
        done=ledger.reserve(rid,BODY)
        self.assertEqual(done.status,"COMPLETED"); self.assertIsNone(done.reservation)
        self.assertFalse(ledger.complete(first.reservation)); self.assertFalse(ledger.uncertain(first.reservation))
    def test_different_body_conflicts_in_every_state(self):
        ledger=self.make()
        for terminal in (None,"complete","uncertain"):
            rid=self.request_id(); first=ledger.reserve(rid,BODY)
            if terminal: getattr(ledger,terminal)(first.reservation)
            result=ledger.reserve(rid,BODY+b" ")
            self.assertEqual(result.status,"CONFLICT"); self.assertIsNone(result.reservation)
    def test_cross_instance_threads_allow_exactly_one(self):
        self.make(); rid=self.request_id(); ledgers=[self.make(initialize=False) for _ in range(8)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(lambda ledger:ledger.reserve(rid,BODY),ledgers))
        self.assertEqual(sum(r.status=="RESERVED" for r in results),1)
        self.assertEqual(sum(r.status=="IN_PROGRESS" for r in results),7)
        self.assertEqual(sum(r.reservation is not None for r in results),1)
    def test_cross_process_reservation_is_serialized(self):
        self.make(); ctx=multiprocessing.get_context("spawn")
        ready,output,start=ctx.Queue(),ctx.Queue(),ctx.Event(); rid=self.request_id()
        children=[ctx.Process(target=reserve_process,args=(str(self.path),rid,BODY,ready,start,output)) for _ in range(4)]
        for child in children: child.start()
        for _ in children: self.assertTrue(ready.get(timeout=10))
        start.set(); states=[output.get(timeout=10) for _ in children]
        for child in children: child.join(10); self.assertEqual(child.exitcode,0)
        self.assertEqual(states.count("RESERVED"),1); self.assertEqual(states.count("IN_PROGRESS"),3)
        ready.close(); output.close()
    def test_crash_and_restart_never_grant_another_attempt(self):
        self.make(); rid=self.request_id(); ctx=multiprocessing.get_context("spawn")
        receive,send=ctx.Pipe(duplex=False); child=ctx.Process(target=crash_after_reserve,args=(str(self.path),rid,send))
        child.start(); send.close(); self.assertTrue(receive.poll(10)); self.assertEqual(receive.recv(),"RESERVED")
        child.join(10); receive.close(); self.assertEqual(child.exitcode,0)
        reopened=self.make(initialize=False)
        self.assertEqual(reopened.reserve(rid,BODY).status,"IN_PROGRESS")
        self.now=1120; self.assertEqual(reopened.reserve(rid,BODY).status,"UNCERTAIN")
        self.now=10_000_000; self.assertEqual(self.make(initialize=False).reserve(rid,BODY).status,"UNCERTAIN")
    def test_expiry_is_exact_and_late_owner_cannot_complete(self):
        ledger=self.make(reservation_ttl=10); rid=self.request_id(); first=ledger.reserve(rid,BODY)
        self.now=1010
        self.assertFalse(ledger.complete(first.reservation)); self.assertFalse(ledger.uncertain(first.reservation))
        self.assertEqual(ledger.reserve(rid,BODY).status,"UNCERTAIN")
        with sqlite3.connect(self.path) as db: self.assertIsNone(db.execute("SELECT owner FROM reservations").fetchone()[0])
    def test_explicit_uncertainty_is_terminal(self):
        ledger=self.make(); rid=self.request_id(); result=ledger.reserve(rid,BODY)
        self.assertTrue(ledger.uncertain(result.reservation)); self.assertFalse(ledger.complete(result.reservation))
        self.assertEqual(ledger.reserve(rid,BODY).status,"UNCERTAIN")
    def test_wrong_lease_is_rejected(self):
        ledger=self.make(); rid=self.request_id(); result=ledger.reserve(rid,BODY)
        forged=dataclasses.replace(result.reservation,_owner=b"x"*32)
        self.assertFalse(ledger.complete(forged)); self.assertEqual(ledger.reserve(rid,BODY).status,"IN_PROGRESS")
        self.assertTrue(ledger.complete(result.reservation))
    def test_capacity_preserves_terminal_tombstones(self):
        ledger=self.make(max_records=2); ids=[self.request_id() for _ in range(2)]
        first=ledger.reserve(ids[0],BODY); second=ledger.reserve(ids[1],BODY)
        ledger.complete(first.reservation); ledger.uncertain(second.reservation); self.now+=1_000_000
        self.assertEqual(ledger.sweep(),0); self.assertEqual(ledger.reserve(self.request_id(),BODY).status,"CAPACITY")
        self.assertEqual(ledger.reserve(ids[0],BODY).status,"COMPLETED")
        self.assertEqual(ledger.reserve(ids[1],BODY).status,"UNCERTAIN")
        self.assertEqual(ledger.reserve(ids[0],b"different").status,"CONFLICT")
        with sqlite3.connect(self.path) as db: self.assertEqual(db.execute("SELECT COUNT(*) FROM reservations").fetchone()[0],2)
    def test_rate_limit_survives_instances_and_restart(self):
        ledger=self.make(rate_limit=2); ids=[self.request_id() for _ in range(3)]
        ledger.complete(ledger.reserve(ids[0],BODY).reservation); ledger.uncertain(ledger.reserve(ids[1],BODY).reservation)
        second=self.make(initialize=False,rate_limit=2); denied=second.reserve(ids[2],BODY)
        self.assertEqual(denied.status,"RATE_LIMITED"); self.assertEqual(denied.retry_after,60); self.assertIsNone(denied.reservation)
        self.assertEqual(second.reserve(ids[0],BODY).status,"COMPLETED")
        self.now=1060; self.assertEqual(second.reserve(ids[2],BODY).status,"RESERVED")
    def test_concurrency_and_expiry_release_only_new_ids(self):
        ledger=self.make(max_inflight=1,reservation_ttl=10); rid=self.request_id(); ledger.reserve(rid,BODY)
        self.assertEqual(ledger.reserve(self.request_id(),BODY).status,"RATE_LIMITED")
        self.now+=10; self.assertEqual(ledger.sweep(),1)
        self.assertEqual(ledger.reserve(rid,BODY).status,"UNCERTAIN")
        self.assertEqual(ledger.reserve(self.request_id(),BODY).status,"RESERVED")
    def test_clock_rollback_cannot_reopen_rate_window(self):
        ledger=self.make(rate_limit=1); result=ledger.reserve(self.request_id(),BODY); ledger.complete(result.reservation)
        self.now=1
        self.assertEqual(self.make(initialize=False,rate_limit=1).reserve(self.request_id(),BODY).status,"RATE_LIMITED")
        with sqlite3.connect(self.path) as db: self.assertEqual(db.execute("SELECT last_now FROM metadata").fetchone()[0],1000)
    def test_clock_jump_expires_without_replaying(self):
        ledger=self.make(); rid=self.request_id(); ledger.reserve(rid,BODY); self.now+=1_000_000
        self.assertEqual(ledger.reserve(rid,BODY).status,"UNCERTAIN")
        self.now=1000; self.assertEqual(ledger.reserve(rid,BODY).status,"UNCERTAIN")
    def test_body_key_owner_and_response_never_persisted(self):
        ledger=self.make(); body=b"SYNTHETIC_PRIVATE_REQUEST_SENTINEL_987654321"
        response=b"SYNTHETIC_PRIVATE_RESPONSE_SENTINEL_123456789"
        result=ledger.reserve(self.request_id(),body); self.assertTrue(ledger.complete(result.reservation))
        for path in self.path.parent.iterdir():
            if path.is_file():
                raw=path.read_bytes()
                for forbidden in (body,response,KEY,result.reservation._owner): self.assertNotIn(forbidden,raw)
                self.assertEqual(stat.S_IMODE(path.stat().st_mode)&0o077,0)
        with sqlite3.connect(self.path) as db: columns={r[1] for r in db.execute("PRAGMA table_info(reservations)")}
        self.assertEqual(columns,{"request_id","fingerprint","state","reserved_at","expires_at","updated_at","owner"})
        self.assertNotIn(result.reservation._owner.hex(),repr(result))
    def test_missing_or_empty_database_needs_explicit_provisioning(self):
        with self.assertRaises(LedgerError): self.make(initialize=False)
        self.assertFalse(self.path.exists()); self.path.touch(mode=0o600)
        with self.assertRaises(LedgerError): self.make(initialize=False)
        self.make(); self.path.unlink()
        with self.assertRaises(LedgerError): self.make(initialize=False)
    def test_wrong_scope_fails_before_expiry_mutation(self):
        ledger=self.make(); ledger.reserve(self.request_id(),BODY); self.now+=1000
        with self.assertRaises(LedgerError): self.make(initialize=False,key=b"different-synthetic-key"*2)
        with sqlite3.connect(self.path) as db: self.assertEqual(db.execute("SELECT state FROM reservations").fetchone()[0],"IN_PROGRESS")
    def test_racing_first_initializers_have_one_scope(self):
        keys=(KEY,b"another-synthetic-scope-key"*2)
        def create(key):
            try: return self.make(key=key)
            except LedgerError: return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool: results=list(pool.map(create,keys))
        self.assertEqual(sum(value is not None for value in results),1)
        winner=next(value for value in results if value is not None)
        self.assertEqual(winner.reserve(self.request_id(),BODY).status,"RESERVED")
    def test_storage_failure_grants_no_permission(self):
        ledger=self.make(busy_timeout_seconds=0.05)
        with sqlite3.connect(self.path,isolation_level=None) as locked:
            locked.execute("BEGIN IMMEDIATE")
            with self.assertRaises(LedgerError): ledger.reserve(self.request_id(),BODY)
            locked.rollback()
        self.path.unlink()
        with self.assertRaises(LedgerError): ledger.reserve(self.request_id(),BODY)
        self.assertFalse(self.path.exists())
    def test_completion_failure_does_not_enable_replay(self):
        ledger=self.make(busy_timeout_seconds=0.05); rid=self.request_id(); result=ledger.reserve(rid,BODY)
        with sqlite3.connect(self.path,isolation_level=None) as locked:
            locked.execute("BEGIN IMMEDIATE")
            with self.assertRaises(LedgerError): ledger.complete(result.reservation)
            locked.rollback()
        self.assertEqual(ledger.reserve(rid,BODY).status,"IN_PROGRESS")
        self.now+=120; self.assertEqual(ledger.reserve(rid,BODY).status,"UNCERTAIN")
    def test_private_permissions_and_symlinks_enforced(self):
        self.make(); self.path.chmod(0o644)
        with self.assertRaises(LedgerError): self.make(initialize=False)
        self.path.chmod(0o600); target=self.path.with_name("real.sqlite"); self.path.rename(target); self.path.symlink_to(target)
        with self.assertRaises(LedgerError): self.make(initialize=False)
    def test_uuid_body_and_clock_bounds(self):
        ledger=self.make(max_body_bytes=8)
        for bad in (None,"","not-a-uuid","A"*36,str(uuid.uuid4()).upper(),"{"+str(uuid.uuid4())+"}"):
            with self.assertRaises(ValueError): ledger.reserve(bad,b"a")
        for bad in (None,"text",b"",b"a"*9):
            with self.assertRaises(ValueError): ledger.reserve(self.request_id(),bad)
        self.assertEqual(ledger.reserve(self.request_id(),b"a"*8).status,"RESERVED")
        self.now=float("nan")
        with self.assertRaises(LedgerError): ledger.reserve(self.request_id(),b"a")
    def test_commit_acknowledgement_loss_never_returns_send_permission(self):
        ledger=self.make(); rid=self.request_id(); connect=ledger._connect
        class LostAcknowledgement:
            def __init__(self,db): self.db=db
            def __getattr__(self,name): return getattr(self.db,name)
            def commit(self):
                self.db.commit()
                raise sqlite3.OperationalError("synthetic COMMIT acknowledgement lost")
        @contextmanager
        def lose_ack():
            with connect() as db: yield LostAcknowledgement(db)
        ledger._connect=lose_ack
        with self.assertRaises(LedgerError): ledger.reserve(rid,BODY)
        ledger._connect=connect
        duplicate=ledger.reserve(rid,BODY)
        self.assertEqual(duplicate.status,"IN_PROGRESS"); self.assertIsNone(duplicate.reservation)
        self.now+=120; self.assertEqual(ledger.reserve(rid,BODY).status,"UNCERTAIN")
    def test_completion_acknowledgement_loss_does_not_replay(self):
        ledger=self.make(); rid=self.request_id(); result=ledger.reserve(rid,BODY); connect=ledger._connect
        class LostAcknowledgement:
            def __init__(self,db): self.db=db
            def __getattr__(self,name): return getattr(self.db,name)
            def commit(self):
                self.db.commit()
                raise sqlite3.OperationalError("synthetic COMMIT acknowledgement lost")
        @contextmanager
        def lose_ack():
            with connect() as db: yield LostAcknowledgement(db)
        ledger._connect=lose_ack
        with self.assertRaises(LedgerError): ledger.complete(result.reservation)
        ledger._connect=connect
        duplicate=ledger.reserve(rid,BODY)
        self.assertEqual(duplicate.status,"COMPLETED"); self.assertIsNone(duplicate.reservation)
    def test_open_instance_refuses_replaced_database(self):
        ledger=self.make(); ledger.reserve(self.request_id(),BODY)
        self.path.rename(self.path.with_name("old.sqlite"))
        replacement=self.make()
        with self.assertRaises(LedgerError): ledger.reserve(self.request_id(),BODY)
        self.assertEqual(replacement.reserve(self.request_id(),BODY).status,"RESERVED")
    def test_configuration_bounds(self):
        for option in ({"max_records":0},{"max_inflight":True},{"rate_limit":-1},{"reservation_ttl":0},{"max_body_bytes":1_048_577},{"busy_timeout_seconds":float("nan")}):
            with self.assertRaises(ValueError): self.make(**option)
        with self.assertRaises(ValueError): self.make(key=b"short")

if __name__=="__main__": unittest.main(verbosity=2)
