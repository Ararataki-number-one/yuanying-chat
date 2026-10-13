"""Real local HTTP barrier controls; no Android execution or APK validation."""
import copy
import importlib.util
from pathlib import Path
import socket
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "profile_update_pause_runner", ROOT / "tests/gecko/run_device.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

CHUNK = 16384
BODY = bytes((index * 29 + 17) % 256 for index in range(3 * CHUNK + 7))
ETAG = '"synthetic-update-v1"'


class PauseTransferBarrierHttpTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="pause-barrier-http-")
        self.previous = (
            runner.OUT, runner.Fixture.pause_barrier,
            runner.Fixture.update_transfer_trace,
            runner.Fixture.update_transfer_counts,
        )
        runner.OUT = Path(self.directory.name)
        (runner.OUT / "update-fixture.apk").write_bytes(BODY)
        runner.Fixture.update_transfer_trace = []
        runner.Fixture.update_transfer_counts = {}
        self.barrier = runner.PauseTransferBarrier(timeout=15)
        runner.Fixture.pause_barrier = self.barrier
        self.connections = []
        self.server = runner.fixture.http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), runner.Fixture
        )
        self.serving = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=.02), daemon=True
        )
        self.serving.start()
        self.addCleanup(self.close_fixture)

    def close_fixture(self):
        self.barrier.abort()
        for connection in self.connections:
            connection.close()
        if self.barrier.reached.is_set():
            self.assertTrue(self.barrier.ended.wait(2), "HTTP barrier leaked a holder")
        self.server.shutdown()
        self.serving.join(2)
        self.server.server_close()
        self.assertFalse(self.serving.is_alive(), "HTTP server did not stop")
        (
            runner.OUT, runner.Fixture.pause_barrier,
            runner.Fixture.update_transfer_trace,
            runner.Fixture.update_transfer_counts,
        ) = self.previous
        self.directory.cleanup()

    def request(self, headers=None):
        connection = socket.create_connection(self.server.server_address, timeout=3)
        self.connections.append(connection)
        request = ["GET /update-transfer/pause HTTP/1.0", "Host: 127.0.0.1"]
        request += [f"{key}: {value}" for key, value in (headers or {}).items()]
        connection.sendall(("\r\n".join(request) + "\r\n\r\n").encode("ascii"))
        received = b""
        while b"\r\n\r\n" not in received:
            chunk = connection.recv(4096)
            self.assertTrue(chunk, "HTTP response closed before headers")
            received += chunk
            self.assertLess(len(received), 65536)
        raw, pending = received.split(b"\r\n\r\n", 1)
        lines = raw.decode("ascii").split("\r\n")
        status = int(lines[0].split()[1])
        response_headers = dict(
            (key.lower(), value.strip())
            for key, value in (line.split(":", 1) for line in lines[1:])
        )
        return connection, status, response_headers, pending

    def held_response(self):
        connection, status, headers, pending = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(int(headers["content-length"]), len(BODY))
        self.assertEqual(headers["etag"], ETAG)
        self.assertTrue(self.barrier.reached.wait(5), "Response never reached its barrier")
        state = self.barrier.snapshot()
        self.assertEqual(state["heldBytes"], 3 * CHUNK)
        self.assertEqual(state["totalBytes"], len(BODY))
        prefix = pending
        while len(prefix) < state["heldBytes"]:
            chunk = connection.recv(state["heldBytes"] - len(prefix))
            self.assertTrue(chunk, "Held response closed before its real prefix")
            prefix += chunk
        self.assertEqual(prefix, BODY[:state["heldBytes"]])
        return connection, prefix

    def assert_still_held(self, connection):
        self.assertFalse(self.barrier.ended.is_set())
        state = self.barrier.snapshot()
        self.assertEqual(state["reason"], "")
        self.assertFalse(state["actualPauseAccepted"])
        connection.settimeout(.15)
        try:
            with self.assertRaises(socket.timeout):
                connection.recv(1)
        finally:
            connection.settimeout(3)

    def read_to_close(self, connection, pending=b""):
        body = pending
        while True:
            chunk = connection.recv(65536)
            if not chunk:
                return body
            body += chunk

    @staticmethod
    def pause_evidence():
        gesture = dict(
            token="real-input-token", label="暂停下载", actualAndroidInput=True,
            actualNativeView=True, enabled=True, clickable=True, windowFocused=True,
        )
        # An accepted pause can precede the transfer worker's final cleanup.
        phase = dict(token="paused-status-token", state="paused", userPaused=True, running=True)
        return gesture, phase

    def test_real_prefix_stays_incomplete_until_accepted_pause_then_exact_range_resumes(self):
        connection, prefix = self.held_response()
        self.assert_still_held(connection)
        gesture, phase = self.pause_evidence()
        self.barrier.accept_pause(gesture, phase)
        self.assertTrue(self.barrier.ended.wait(2))
        self.assertEqual(self.read_to_close(connection), b"", "Pause released the final bytes")
        state = self.barrier.snapshot()
        self.assertEqual(state["reason"], "actual-pause-accepted")
        self.assertTrue(state["actualPauseAccepted"])
        self.assertTrue(state["runningAtAcceptance"])
        self.assertLessEqual(state["reachedAt"], state["pauseAcceptedAt"])
        self.assertLessEqual(state["pauseAcceptedAt"], state["endedAt"])
        self.assertLess(state["endedAt"], state["deadline"])
        first = runner.Fixture.update_transfer_trace[0]
        self.assertEqual(first["sentBytes"], len(prefix))
        self.assertEqual(first["returnedBytes"], len(prefix))

        resumed, status, headers, pending = self.request(
            {"Range": f"bytes={len(prefix)}-", "If-Range": ETAG}
        )
        self.assertEqual(status, 206)
        self.assertEqual(headers["content-range"], f"bytes {len(prefix)}-{len(BODY)-1}/{len(BODY)}")
        self.assertEqual(headers["etag"], ETAG)
        self.assertEqual(int(headers["content-length"]), len(BODY) - len(prefix))
        remaining = self.read_to_close(resumed, pending)
        self.assertEqual(remaining, BODY[len(prefix):])
        self.assertEqual(prefix + remaining, BODY)
        second = runner.Fixture.update_transfer_trace[1]
        self.assertEqual(second["ifRange"], ETAG)
        self.assertEqual(second["range"], f"bytes={len(prefix)}-")
        self.assertNotIn("pauseBarrier", second)
        self.assertEqual(second["returnedBytes"], len(remaining))

    def test_counterfeit_gesture_and_unaccepted_phase_cannot_release_http_tail(self):
        connection, _ = self.held_response()
        gesture, phase = self.pause_evidence()
        invalid = [(dict(gesture, **{key: False}), phase) for key in (
            "actualAndroidInput", "actualNativeView", "enabled", "clickable", "windowFocused"
        )]
        invalid += [
            (dict(gesture, label="继续下载"), phase),
            (gesture, dict(phase, state="ready")),
            (gesture, dict(phase, userPaused=False)),
        ]
        for rejected_gesture, rejected_phase in invalid:
            with self.subTest(gesture=rejected_gesture, phase=rejected_phase):
                before = copy.deepcopy(self.barrier.snapshot())
                with self.assertRaises(AssertionError):
                    self.barrier.accept_pause(rejected_gesture, rejected_phase)
                self.assertEqual(self.barrier.snapshot(), before)
        self.assert_still_held(connection)
        self.barrier.abort()
        self.assertTrue(self.barrier.ended.wait(2))
        self.assertEqual(self.read_to_close(connection), b"")
        self.assertEqual(self.barrier.snapshot()["reason"], "cleanup")

    def test_client_disconnect_ends_holder_without_sending_tail(self):
        connection, prefix = self.held_response()
        connection.shutdown(socket.SHUT_RDWR)
        connection.close()
        self.assertTrue(self.barrier.ended.wait(2))
        state = self.barrier.snapshot()
        self.assertEqual(state["reason"], "client-disconnect")
        self.assertFalse(state["actualPauseAccepted"])
        self.assertGreaterEqual(state["endedAt"], state["reachedAt"])
        self.assertEqual(runner.Fixture.update_transfer_trace[0]["sentBytes"], len(prefix))
        # Production cancellation may close its socket before the host records
        # the gesture and paused phase. That order still admits real evidence.
        self.barrier.accept_pause(*self.pause_evidence())
        accepted = self.barrier.snapshot()
        self.assertEqual(accepted["reason"], "client-disconnect")
        self.assertTrue(accepted["actualPauseAccepted"])

    def test_deadline_closes_incomplete_response_and_rejects_late_acknowledgement(self):
        self.barrier = runner.PauseTransferBarrier(timeout=.4)
        runner.Fixture.pause_barrier = self.barrier
        connection, prefix = self.held_response()
        self.assertTrue(self.barrier.ended.wait(2))
        self.assertEqual(self.read_to_close(connection), b"")
        state = self.barrier.snapshot()
        self.assertEqual(state["reason"], "deadline")
        self.assertFalse(state["actualPauseAccepted"])
        self.assertGreaterEqual(state["endedAt"], state["deadline"])
        self.assertEqual(runner.Fixture.update_transfer_trace[0]["returnedBytes"], len(prefix))
        with self.assertRaises(AssertionError):
            self.barrier.accept_pause(*self.pause_evidence())


if __name__ == "__main__":
    unittest.main()
