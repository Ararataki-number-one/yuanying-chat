"""Run channel discovery/state controls in the existing source-bound host lane."""
import unittest
import profile_experience46_hosts_test as existing_hosts


class UpdateChannelHosts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        existing_hosts.Experience46Hosts.setUpClass.__func__(cls)

    host = existing_hosts.Experience46Hosts.host

    def test_channel_discovery_and_download_ownership(self):
        for jar in (self.desktop, self.android):
            with self.subTest(json_runtime=jar.name):
                self.host('update-channels', 'tests/update-channels-host/run.py', jar)


if __name__ == '__main__':
    unittest.main(verbosity=2)
