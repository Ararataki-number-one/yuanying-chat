import unittest
import profile_experience46_hosts_test as existing_hosts

class ChatDownloadProgressControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        existing_hosts.Experience46Hosts.setUpClass.__func__(cls)
    host=existing_hosts.Experience46Hosts.host
    def test_real_progress_counters_and_environment_ownership(self):
        for jar in (self.desktop,self.android):
            with self.subTest(json_runtime=jar.name):
                self.host('chat-download-progress','tests/chat-download-progress-host/run.py',jar)

if __name__=='__main__':unittest.main(verbosity=2)
