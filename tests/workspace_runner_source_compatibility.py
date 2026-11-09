"""Finite workspace-navigation source views for retained historical oracles.

The actual device runner executes its current workspace roundtrip. Only the
explicit historical input ports below may restore the c244 public Git bytes.
Every after-image, before-image and local context is locked in full; this is not
runtime acceptance, an alternate runner, or a general source filter.
"""
import functools
import hashlib

BASE_COMMIT = 'c244835a4c1e3629909b2b1ce132ca5987a97d9a'
BASE_TREE = '13f8feea716e7ceebd71fb46b21966292c920681'
RUNNER = 'tests/gecko/run_device.py'
ROWS = {
  "tests/gecko/run_device.py": {
    "beforeGitBlob": "6684144bbbf6c31d798703b483c8d4fd951eec9e",
    "beforeBytes": 92698,
    "beforeSha256": "18340d331bc78f1e8033bad4f4de2399a4b3bd9c417214e87551f8967cfe5474",
    "afterBytes": 92799,
    "afterSha256": "05effe15567c088287ebc4ba28c2e46c4a6800db934e59b07a3ead2592b47f79",
    "deltas": [
      {
        "before": "        adb('shell','uiautomator','dump','/sdcard/gecko-production.xml')\n        hierarchy=adb('shell','cat','/sdcard/gecko-production.xml')\n        (OUT/'production-ui.xml').write_text(hierarchy)\n        for label in ['会话','环境','下载','网络','设置']:assert label in hierarchy,(label,hierarchy)\n        assert not any(node.attrib.get('text') in ['简洁','原网页'] for node in ET.fromstring(hierarchy).iter('node')),hierarchy\n        assert 'FATAL EXCEPTION' not in adb('logcat','-d','-s','AndroidRuntime:E','*:S')\n        update_checks=[]\n",
        "after": "        adb('shell','uiautomator','dump','/sdcard/gecko-production.xml')\n        hierarchy=adb('shell','cat','/sdcard/gecko-production.xml')\n        (OUT/'production-ui.xml').write_text(hierarchy)\n        from workspace_navigation_contract import exercise_workspace_roundtrip\n        report['productionNavigation']=exercise_workspace_roundtrip(adb,hierarchy,lambda name,xml:(OUT/name).write_text(xml),package)\n        assert not any(node.attrib.get('text') in ['简洁','原网页'] for node in ET.fromstring(hierarchy).iter('node')),hierarchy\n        assert 'FATAL EXCEPTION' not in adb('logcat','-d','-s','AndroidRuntime:E','*:S')\n        update_checks=[]\n",
        "beforeSha256": "d3d927a35fb03eb0fa38f67d72db5df53871be39f02d57ee721ffcbc14c39ea6",
        "afterSha256": "4610ce5f02974cf1384052f7e9f61f1828b648c21798acf1d4fd80ab1bb23b69"
      }
    ]
  },
  "tests/event_journal_source_compatibility.py": {
    "beforeGitBlob": "db25ee59e66611de45d03b2313876bff37b486f3",
    "beforeBytes": 5971,
    "beforeSha256": "b35122f03dca997a2b5e3f25675371ec4f8f83d77e5a8ca2fbac7d40079fde31",
    "afterBytes": 6185,
    "afterSha256": "c35065cb4a6ecc7f5705bdf5ddd88d9799e3150c709685edb963df893cb30895",
    "deltas": [
      {
        "before": "    if hashlib.sha256(dump(restored).encode()).hexdigest() != row['previousSha256']:\n        raise ValueError('Receipt journal AST inverse did not restore the complete original run AST')\n    return restored\n",
        "after": "    if hashlib.sha256(dump(restored).encode()).hexdigest() != row['previousSha256']:\n        raise ValueError('Receipt journal AST inverse did not restore the complete original run AST')\n    return restored\n\n\n# Exact workspace-navigation source view for historical metadata only.\nfrom workspace_runner_source_compatibility import wrap_input as _workspace_source_input\nsource_input = _workspace_source_input(source_input)\n",
        "beforeSha256": "64f9bf288af1f1177684c96047249e843f3097edd0226fa6be3147ceb969dd02",
        "afterSha256": "8e903003fd09a4a54ea9d674d0993203b0b6ecc3fd04125715cc7ad157a2ee12"
      }
    ]
  },
  "tests/profile_event_journal_source_compatibility_test.py": {
    "beforeGitBlob": "9254807dff3a5200b57e2b0a64593332297a9df3",
    "beforeBytes": 10423,
    "beforeSha256": "c9721b377cd970c3e8947aee35d758102be2a2eb098e9e86371369afc8ff5b3e",
    "afterBytes": 10584,
    "afterSha256": "90fbaefd211064a39942775340e4dee2cf830d7dcd2aa2c5efdc3e50c985695e",
    "deltas": [
      {
        "before": "\nimport event_journal_source_compatibility as journal\nimport experience46_source_compatibility as experience\n\nROOT = Path(__file__).resolve().parents[1]\nRUNNER = 'tests/gecko/run_device.py'\n",
        "after": "\nimport event_journal_source_compatibility as journal\nimport experience46_source_compatibility as experience\nfrom workspace_runner_source_compatibility import historical_input as workspace_source_input\n\nROOT = Path(__file__).resolve().parents[1]\nRUNNER = 'tests/gecko/run_device.py'\n",
        "beforeSha256": "859310fdb94d2577d930e432ff06a11ff603dbd102a778cba775cd863a96633e",
        "afterSha256": "e09a499cb18a83e80f8463f5289e7ae862b7aafd74d82cba78734eb7c8a8e38a"
      },
      {
        "before": "        for relative, row in journal.manifest()['files'].items():\n            with self.subTest(path=relative):\n                previous = subprocess.check_output(['git', 'show', journal.BASE_COMMIT + ':' + relative], cwd=ROOT)\n                current = (ROOT / relative).read_bytes()\n                if relative in ('tests/experience46_source_compatibility.py', 'tests/profile_experience46_source_compatibility_test.py'):\n                    from dual_browser_source_compatibility import source_input\n                    current = source_input(current, relative)\n",
        "after": "        for relative, row in journal.manifest()['files'].items():\n            with self.subTest(path=relative):\n                previous = subprocess.check_output(['git', 'show', journal.BASE_COMMIT + ':' + relative], cwd=ROOT)\n                current = workspace_source_input((ROOT / relative).read_bytes(), relative)\n                if relative in ('tests/experience46_source_compatibility.py', 'tests/profile_experience46_source_compatibility_test.py'):\n                    from dual_browser_source_compatibility import source_input\n                    current = source_input(current, relative)\n",
        "beforeSha256": "4e6ef1cdc285d4047121900589672dc28f41ad5dc5faab008db036db54923088",
        "afterSha256": "60f44efdddb6d296d7306ef5c619d970d53a64b31a718349a6c1984a99dd8baa"
      },
      {
        "before": "    def test_missing_duplicate_changed_relocated_and_unknown_bytes_are_rejected(self):\n        rejected = 0\n        for relative, row in journal.manifest()['files'].items():\n            current = (ROOT / relative).read_bytes()\n            if relative in ('tests/experience46_source_compatibility.py', 'tests/profile_experience46_source_compatibility_test.py'):\n                from dual_browser_source_compatibility import source_input\n                current = source_input(current, relative)\n",
        "after": "    def test_missing_duplicate_changed_relocated_and_unknown_bytes_are_rejected(self):\n        rejected = 0\n        for relative, row in journal.manifest()['files'].items():\n            current = workspace_source_input((ROOT / relative).read_bytes(), relative)\n            if relative in ('tests/experience46_source_compatibility.py', 'tests/profile_experience46_source_compatibility_test.py'):\n                from dual_browser_source_compatibility import source_input\n                current = source_input(current, relative)\n",
        "beforeSha256": "b3a8af6af2dfcd80c22ec3387e7c0672e2f5f8123de97e4e7d515ed40b95b42a",
        "afterSha256": "43844880e1c41d3c3cb10403dee849973fd1c84d93350b7126f5318b888e7c11"
      }
    ]
  },
  "tests/dual_browser_source_compatibility.py": {
    "beforeGitBlob": "24523cd6c3fe302d03a4e4a893b1d4569a6ca340",
    "beforeBytes": 5199,
    "beforeSha256": "2f36e797407ecee55bce6545c461ad9b0fb4879bb4d01b1e8e6378122efc6cf8",
    "afterBytes": 5413,
    "afterSha256": "0fee82b58253f2cc7a3f292826d9eb0c9100ea0beaf5fdd1277e229ed12f48e2",
    "deltas": [
      {
        "before": "    if len(raw) != row['previousBytes'] or _sha(raw) != row['previousSha256']:\n        raise ValueError('Dual-browser inverse did not restore the complete original source')\n    return raw\n",
        "after": "    if len(raw) != row['previousBytes'] or _sha(raw) != row['previousSha256']:\n        raise ValueError('Dual-browser inverse did not restore the complete original source')\n    return raw\n\n\n# Exact workspace-navigation source view for historical metadata only.\nfrom workspace_runner_source_compatibility import wrap_input as _workspace_source_input\nsource_input = _workspace_source_input(source_input)\n",
        "beforeSha256": "a43b7c41beb78cabe170c3c46f18d70811ff908aaf76551aa68d57a152e98f4a",
        "afterSha256": "455bd7e5c2ccba76d18004d017451317738e04456b0187597bf25f9507f3e411"
      }
    ]
  },
  "tests/profile_fixture_root_source_compatibility.py": {
    "beforeGitBlob": "2418e56b2c234de9fe9e053c852a7960203858d2",
    "beforeBytes": 6610,
    "beforeSha256": "c79732d202afa92e1d76ee2f48dea13221d973f3813433d0b1cfe2d61e7df619",
    "afterBytes": 6884,
    "afterSha256": "48cecc406c65ace02e52091b296eba617f8ee1b7a45fc1e19f66dcd6b5c8ae0f",
    "deltas": [
      {
        "before": "from gradle_workflow_test_source_compatibility import wrap_root_source_input as _gradle_root_source_input, wrap_root_manifest as _gradle_root_manifest\nsource_input = _gradle_root_source_input(source_input)\nmanifest = _gradle_root_manifest(manifest)\n",
        "after": "from gradle_workflow_test_source_compatibility import wrap_root_source_input as _gradle_root_source_input, wrap_root_manifest as _gradle_root_manifest\nsource_input = _gradle_root_source_input(source_input)\nmanifest = _gradle_root_manifest(manifest)\n\n# Exact workspace-navigation source view for historical metadata only.\nfrom workspace_runner_source_compatibility import wrap_input as _workspace_source_input\nsource_input = _workspace_source_input(source_input)\nhistorical_input = _workspace_source_input(historical_input)\n",
        "beforeSha256": "0b9a7c9dd0be997ad1eb13b2d5686823362bf4beacdfdaaee43fef5879f637a9",
        "afterSha256": "98ff098584cf94e844fcd00f1e33d871b3538ed3fe1b5018ec0bbf5df4508a96"
      }
    ]
  },
  "tests/profile_fixture_root_source_compatibility_test.py": {
    "beforeGitBlob": "fae4c6a5d3586a8171ce459fafdb5e822d1f55f7",
    "beforeBytes": 13619,
    "beforeSha256": "5141e844f835aae454265c3e01cb36d9f2869dabd23ef4047eedd9f1423acd8f",
    "afterBytes": 13780,
    "afterSha256": "d5296bfb6d3a8c12f6cc7fc4537dde2024030c7bf8a3aab87768072200bb4cc0",
    "deltas": [
      {
        "before": "from unittest.mock import patch\n\nimport profile_fixture_root_source_compatibility as layer\n\nROOT = Path(__file__).resolve().parents[1]\nSHA = lambda raw: hashlib.sha256(raw).hexdigest()\n",
        "after": "from unittest.mock import patch\n\nimport profile_fixture_root_source_compatibility as layer\nfrom workspace_runner_source_compatibility import historical_input as workspace_source_input\n\nROOT = Path(__file__).resolve().parents[1]\nSHA = lambda raw: hashlib.sha256(raw).hexdigest()\n",
        "beforeSha256": "d1797bd924ffc09222c979db115b6f7ca75a2ec0e7a970677e2541e32ec1425a",
        "afterSha256": "14658977fac4c3a08474567615d916a666f20fda6ddd8eb4b17fe28b688bd645"
      },
      {
        "before": "        self.assertEqual(set(BEFORE), layer.PATHS)\n        self.assertEqual(sum(len(r['deltas']) for r in value['files'].values()), 7)\n        for relative, row in value['files'].items():\n            current = (ROOT/relative).read_bytes()\n            previous = layer.source_input(current, relative)\n            self.assertEqual((SHA(previous), len(previous)), BEFORE[relative])\n            self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))\n",
        "after": "        self.assertEqual(set(BEFORE), layer.PATHS)\n        self.assertEqual(sum(len(r['deltas']) for r in value['files'].values()), 7)\n        for relative, row in value['files'].items():\n            current = workspace_source_input((ROOT/relative).read_bytes(), relative)\n            previous = layer.source_input(current, relative)\n            self.assertEqual((SHA(previous), len(previous)), BEFORE[relative])\n            self.assertEqual((SHA(current), len(current)), (row['reviewedSha256'], row['reviewedBytes']))\n",
        "beforeSha256": "ab8fae197eae79cc570a273ef59eb4f76ab47ac7e4f0310096b3846b49192a34",
        "afterSha256": "1832e5ab8441f9ea5934df176eebd88b6b38c969e3b41d14b78a7b2db6119f34"
      },
      {
        "before": "    def test_missing_duplicate_changed_moved_truncated_and_unknown_owned_images_reject(self):\n        rejected = 0\n        for relative, row in layer.manifest()['files'].items():\n            raw = (ROOT/relative).read_bytes()\n            for delta in row['deltas']:\n                chunk = delta['current'].encode()\n                self.assertEqual(raw.count(chunk), 1)\n",
        "after": "    def test_missing_duplicate_changed_moved_truncated_and_unknown_owned_images_reject(self):\n        rejected = 0\n        for relative, row in layer.manifest()['files'].items():\n            raw = workspace_source_input((ROOT/relative).read_bytes(), relative)\n            for delta in row['deltas']:\n                chunk = delta['current'].encode()\n                self.assertEqual(raw.count(chunk), 1)\n",
        "beforeSha256": "d11fc7f28aa4b372c380106f36a6fca9edb3ab832bd3922831569e0724c15160",
        "afterSha256": "7f07ad6e73c6ea7ddef30ba3dd4485c960ee7ae98ea520e197e69c85bfc76c7f"
      }
    ]
  },
  "tests/gradle_workflow_test_source_compatibility.py": {
    "beforeGitBlob": "235ba0d522a3af5e86816cfd6534f9cb8d8133fc",
    "beforeBytes": 7698,
    "beforeSha256": "f92a7479ca6e00ce3b86e80f5335d5f0d34292485a927c8c7d2169f8de5a8953",
    "afterBytes": 7973,
    "afterSha256": "b501712bea7db013dfda421e265fc07f64880958083bd89b6c507647ae7c89ef",
    "deltas": [
      {
        "before": "    def historical_helper(raw):\n        return original(historical_input(raw, FINAL))\n    return historical_helper\n",
        "after": "    def historical_helper(raw):\n        return original(historical_input(raw, FINAL))\n    return historical_helper\n\n\n# Exact workspace-navigation source view for historical metadata only.\nfrom workspace_runner_source_compatibility import wrap_input as _workspace_source_input\nsource_input = _workspace_source_input(source_input)\nhistorical_input = _workspace_source_input(historical_input)\n",
        "beforeSha256": "10178d9d45f20d7cbf78c1f4498f99872311c38649ea238f7c9681c8074442ce",
        "afterSha256": "560145e3354729c5a8d5b1b5b51aa9e2b8eaed4d6bb87fb9c2daaeac7eeae414"
      }
    ]
  },
  "tests/profile_gradle_workflow_test_source_compatibility_test.py": {
    "beforeGitBlob": "9cccb334856513cff2ae1bcffb9d1e2c0945604c",
    "beforeBytes": 6740,
    "beforeSha256": "7546f7a434ed3df4aff2cd33be578ad789a05b8025f16955c8485cfa602799c2",
    "afterBytes": 6893,
    "afterSha256": "5563bda90d57ad303973dbaaabc571bf9bd007d0656a94e3babe57a8b65591ba",
    "deltas": [
      {
        "before": "\nimport final_browser_source_compatibility as final\nimport gradle_workflow_test_source_compatibility as inputs\nimport profile_fixture_root_source_compatibility_test as root_controls\nimport profile_resource_startup_source_compatibility_test as resource_controls\n\n",
        "after": "\nimport final_browser_source_compatibility as final\nimport gradle_workflow_test_source_compatibility as inputs\nfrom workspace_runner_source_compatibility import historical_input as workspace_source_input\nimport profile_fixture_root_source_compatibility_test as root_controls\nimport profile_resource_startup_source_compatibility_test as resource_controls\n\n",
        "beforeSha256": "f22bcde2a3cc83b66f93fc5f6193725f87fbf2a21689ac10d6e8642ebf391cf1",
        "afterSha256": "e3e8114098e5a0beedaa003b4836e37f62f53c4ef7c9fd1b134a405beefbb197"
      },
      {
        "before": "        value = inputs.manifest()\n        self.assertEqual(git('rev-parse', value['baseCommit'] + '^{tree}').decode().strip(), value['baseTree'])\n        for path, row in value['files'].items():\n            raw = (ROOT / path).read_bytes()\n            before = git('show', value['baseCommit'] + ':' + path)\n            self.assertEqual(inputs.source_input(raw, path), before)\n            self.assertEqual((inputs.sha(before), len(before)), (row['previousSha256'], row['previousBytes']))\n",
        "after": "        value = inputs.manifest()\n        self.assertEqual(git('rev-parse', value['baseCommit'] + '^{tree}').decode().strip(), value['baseTree'])\n        for path, row in value['files'].items():\n            raw = workspace_source_input((ROOT / path).read_bytes(), path)\n            before = git('show', value['baseCommit'] + ':' + path)\n            self.assertEqual(inputs.source_input(raw, path), before)\n            self.assertEqual((inputs.sha(before), len(before)), (row['previousSha256'], row['previousBytes']))\n",
        "beforeSha256": "cf7050292938f704343d40bb9f71c5af9e25ee28178226084c3f219fb3ce2ce3",
        "afterSha256": "f8c8f58eff8e0864072862f1b9185559e6f4874fd7798166119b714edf423c42"
      },
      {
        "before": "\n    def test_actual_after_context_mutations_still_face_original_guards(self):\n        for path, row in inputs.manifest()['files'].items():\n            raw = (ROOT / path).read_bytes()\n            candidates = [raw + b' ', raw[:1000], b'unknown source']\n            for delta in row['deltas']:\n                current = delta['current'].encode()\n",
        "after": "\n    def test_actual_after_context_mutations_still_face_original_guards(self):\n        for path, row in inputs.manifest()['files'].items():\n            raw = workspace_source_input((ROOT / path).read_bytes(), path)\n            candidates = [raw + b' ', raw[:1000], b'unknown source']\n            for delta in row['deltas']:\n                current = delta['current'].encode()\n",
        "beforeSha256": "ed9c69d5de7af17a967359b27ecfaa75b666a85852ce2708b56ebbbc7879a090",
        "afterSha256": "a23d1909fc7d8d9841999193544652e8b21f4be33eb33701d3e12a150d815aac"
      }
    ]
  },
  "tests/profile_resource_startup_source_compatibility_test.py": {
    "beforeGitBlob": "29d4c8cf3b3c56d428ab328bcdb5a24d6b18a349",
    "beforeBytes": 11326,
    "beforeSha256": "e02d699c106df7827230d885080a1c0ff73b62e17428ac4034fe5e74e371af26",
    "afterBytes": 11483,
    "afterSha256": "f86e3cd552b2a307d2607ddfa224832f429367fcae607832c8b977c067dc7f5a",
    "deltas": [
      {
        "before": "from unittest.mock import patch\n\nimport resource_startup_source_compatibility as layer\n\nROOT = Path(__file__).resolve().parents[1]\nSHA = lambda raw: hashlib.sha256(raw).hexdigest()\n",
        "after": "from unittest.mock import patch\n\nimport resource_startup_source_compatibility as layer\nfrom workspace_runner_source_compatibility import historical_input as workspace_source_input\n\nROOT = Path(__file__).resolve().parents[1]\nSHA = lambda raw: hashlib.sha256(raw).hexdigest()\n",
        "beforeSha256": "98a96ac93766b0eacae92a3f0adc934ee40a38397623ff024f5929681b09e801",
        "afterSha256": "0b220a87a38878f6a11557fdcc3066de4f5d5634f5c971a56c6cdcaa5f7e11e7"
      },
      {
        "before": "        self.assertEqual(set(cfg['sources']), set(layer.SOURCE_PATHS))\n        for relative, row in cfg['sources'].items():\n            with self.subTest(path=relative):\n                current = (ROOT/relative).read_bytes()\n                previous = layer.source_input(current, relative)\n                self.assertEqual((SHA(previous), len(previous)), (row['previousSha256'], row['previousBytes']))\n                forward = previous\n",
        "after": "        self.assertEqual(set(cfg['sources']), set(layer.SOURCE_PATHS))\n        for relative, row in cfg['sources'].items():\n            with self.subTest(path=relative):\n                current = workspace_source_input((ROOT/relative).read_bytes(), relative)\n                previous = layer.source_input(current, relative)\n                self.assertEqual((SHA(previous), len(previous)), (row['previousSha256'], row['previousBytes']))\n                forward = previous\n",
        "beforeSha256": "cdb0dcb8b0b306f911fa8c67cc1bca3b41815add63f65fe507ce563b98c52769",
        "afterSha256": "cb31cde2898ec160db07e2e812c9e8a31211c13fc29d62f5fda585732d77f4eb"
      },
      {
        "before": "    def test_each_missing_duplicate_changed_moved_unknown_and_foreign_image_rejects(self):\n        rejected = 0\n        for path, row in layer.config()['sources'].items():\n            current = (ROOT/path).read_bytes()\n            for delta in row['edits']:\n                chunk = delta['current'].encode()\n                remainder = current.replace(chunk, b'', 1)\n",
        "after": "    def test_each_missing_duplicate_changed_moved_unknown_and_foreign_image_rejects(self):\n        rejected = 0\n        for path, row in layer.config()['sources'].items():\n            current = workspace_source_input((ROOT/path).read_bytes(), path)\n            for delta in row['edits']:\n                chunk = delta['current'].encode()\n                remainder = current.replace(chunk, b'', 1)\n",
        "beforeSha256": "73e5f79d10ff449cc652be43f1aec5b1f7176d2bca03dad8050924716de39782",
        "afterSha256": "64a89e0c00e1baa7a5d065c91e2b9b28462a8347101207426732d82e5e844ee9"
      }
    ]
  },
  "tests/resource_startup_source_compatibility.py": {
    "beforeGitBlob": "2b27feeb14b92335a3b3569bd08133fc5aaced1e",
    "beforeBytes": 7486,
    "beforeSha256": "985a98c85746b9d8736edbcad689a69caf151c6b91a648429a41a282c8bcc8a5",
    "afterBytes": 7699,
    "afterSha256": "84877c597c2e49a15bcc988ecb7cb7c57321f188476e33e2ff2e5b213741f763",
    "deltas": [
      {
        "before": "# Exact after-image rows; original resource guards and forward contexts remain.\nfrom gradle_workflow_test_source_compatibility import wrap_resource_config as _gradle_resource_config\nconfig = _gradle_resource_config(config)\n",
        "after": "# Exact after-image rows; original resource guards and forward contexts remain.\nfrom gradle_workflow_test_source_compatibility import wrap_resource_config as _gradle_resource_config\nconfig = _gradle_resource_config(config)\n\n# Exact workspace-navigation source view for historical metadata only.\nfrom workspace_runner_source_compatibility import wrap_input as _workspace_source_input\nsource_input = _workspace_source_input(source_input)\n",
        "beforeSha256": "5e9da7f8004116f999fe04ce61bebd470dd6ac1aecf902110804449ccd8abcbb",
        "afterSha256": "df9655cc3e2bcf4973310bf1437ff9164d03471445fddfe20cd14c777c43548b"
      }
    ]
  }
}


PATHS = frozenset(ROWS)
MAX_SOURCE_BYTES = 256 * 1024


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source_input(raw, relative):
    """One complete declared after-image -> its exact c244 Git blob."""
    if (type(raw) is not bytes or type(relative) is not str or relative not in PATHS
            or not 0 < len(raw) <= MAX_SOURCE_BYTES):
        raise ValueError('Workspace history requires complete bytes and an exact owned path')
    row = ROWS[relative]
    if (len(raw), sha(raw)) != (row['afterBytes'], row['afterSha256']):
        raise ValueError('Workspace history rejects unknown complete after-image')
    for delta in reversed(row['deltas']):
        current, previous = delta['after'].encode('utf-8'), delta['before'].encode('utf-8')
        if (not current or not previous or current == previous or raw.count(current) != 1
                or sha(current) != delta['afterSha256'] or sha(previous) != delta['beforeSha256']):
            raise ValueError('Workspace history requires every exact local context once')
        raw = raw.replace(current, previous, 1)
    if (len(raw), sha(raw)) != (row['beforeBytes'], row['beforeSha256']):
        raise ValueError('Workspace history did not restore the complete c244 predecessor')
    blob = hashlib.sha1(('blob '+str(len(raw))+'\0').encode()+raw).hexdigest()
    if blob != row['beforeGitBlob']:
        raise ValueError('Workspace history did not restore the declared actual Git blob')
    return raw


def historical_input(raw, relative):
    """Only exact after-images change; all other inputs face the old guard."""
    if type(raw) is bytes and type(relative) is str and relative in PATHS:
        row = ROWS[relative]
        if (len(raw), sha(raw)) == (row['afterBytes'], row['afterSha256']):
            return source_input(raw, relative)
    return raw


def wrap_input(original):
    """Explicit historical module port; never modify filesystem or producers."""
    @functools.wraps(original)
    def historical_source(raw, relative):
        return original(historical_input(raw, relative), relative)
    return historical_source
