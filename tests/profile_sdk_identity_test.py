"""Synthetic rejection controls; no Android, APK correctness or repair acceptance."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import warnings
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prototype_sdk_contract', ROOT/'tools/gecko/sdk_identity_contract.py')
sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sdk)
SOURCE, TREE = 'a'*40, 'b'*40


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def fixture():
    patch, recipe = b'synthetic source diff\n', b'synthetic reproducible compile recipe\n'
    manifest = dict(schema=1, sdkBuildKind='source-derived-java', sdkCoordinate=sdk.SDK_COORDINATE,
                    sdkRuntimeCoordinate=sdk.SDK_RUNTIME_COORDINATE, sdkInputCoordinate=sdk.SDK_COORDINATE,
                    sdkInputAarSha256=sdk.SDK_AAR_SHA256, sdkAarSha256='ede7935705aff417b9f5af0470f553ea55672680419bc61e9a49f64192cd4876', sdkAarBytes=241628049,
                    sdkClassesJarSha256='199f0506b699f23a6ee899b93b759e29bec4f14599ca46a3e8b7b2b2ba6865df', sdkGeckoEditableClassSha256=sdk.DERIVED_EDITABLE_SHA256,
                    upstreamRevision=sdk.UPSTREAM_REVISION,
                    sourcePatch=dict(path='third-party/patches/editable.patch', bytes=len(patch), sha256=sdk.digest(patch)),
                    sourceRecipe=dict(path='tools/gecko/build_editable_sdk.py', bytes=len(recipe), sha256=sdk.digest(recipe)),
                    **copy.deepcopy(sdk.DERIVED_FLAGS))
    raw = encoded(manifest)
    materials = {sdk.DERIVED_MANIFEST: raw, manifest['sourcePatch']['path']: patch,
                 manifest['sourceRecipe']['path']: recipe,
                 'app/src/main/java/local/pocketchat/GeckoWebView.java': b'static final String VERSION="GeckoView 157.0.1 (source-derived Java editable-selection)";'}
    def reader(source, path):
        if source != SOURCE:
            raise ValueError('foreign selected source')
        return materials[path]
    receipt = dict(manifest, sourceCommit=SOURCE, sourceTree=TREE, runId='42', runAttempt='1', sdkManifestSha256=sdk.digest(raw))
    receipt_raw = encoded(receipt)
    asset = sdk.identity_from_receipt(receipt_raw, manifest, sdk.digest(raw), SOURCE, TREE)
    installed = dict(schema=1, package='local.pocketchat.test', sourceCommit=SOURCE, sourceTree=TREE,
                     dirtySource=False, version='2.0.0', versionCode=53, sdkCoordinate=sdk.SDK_COORDINATE,
                     apkSha256='e'*64, apkBytes=123, buildStampSha256='f'*64, sdkBuildIdentity=asset)
    report = dict(buildIdentity=installed, engineVersion='GeckoView 157.0.1 (source-derived Java editable-selection)',
                  **{key: asset[key] for key in sdk.SDK_FIELDS})
    return manifest, materials, reader, receipt, receipt_raw, asset, installed, report


class SelectedSourceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.materials, self.reader, self.receipt, self.raw, self.asset, self.installed, self.report = fixture()

    def rejects_identity(self, change):
        value = copy.deepcopy(self.installed)
        change(value)
        with self.assertRaises((ValueError, KeyError)):
            sdk.verify_sdk_identity(value, SOURCE, TREE, self.raw, self.reader)

    def test_exact_source_receipt_and_asset_are_bound(self):
        self.assertEqual(sdk.verify_sdk_identity(self.installed, SOURCE, TREE, self.raw, self.reader), self.asset)
        self.assertEqual(sdk.verify_report_sdk(self.report, self.report, self.reader), self.asset)

    def test_legacy_official_identity_remains_accepted(self):
        value = dict(schema=1, sdkCoordinate=sdk.SDK_COORDINATE, sourceCommit=SOURCE, sourceTree=TREE)
        def official_reader(source, path):
            raise KeyError(path)
        self.assertEqual(sdk.verify_sdk_identity(value, reader=official_reader), value)
        sdk.verify_report_sdk(dict(buildIdentity=value, sdkCoordinate=sdk.SDK_COORDINATE,
                                   sdkAarSha256=sdk.SDK_AAR_SHA256, engineVersion='GeckoView 157.0.1'), reader=official_reader)

    def test_missing_sdk_asset_cannot_downgrade_selected_derived_source(self):
        self.rejects_identity(lambda value: value.pop('sdkBuildIdentity'))

    def test_official_build_kind_cannot_downgrade_selected_derived_source(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkBuildKind='official'))

    def test_unknown_build_kind_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkBuildKind='anything-derived'))

    def test_foreign_runtime_coordinate_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkRuntimeCoordinate='local.attacker:sdk:any'))

    def test_official_checksum_cannot_describe_actual_derived_sdk(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkAarSha256=sdk.SDK_AAR_SHA256))

    def test_sdk_output_cannot_self_authorize(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkAarSha256='0'*64))

    def test_wrong_classes_hash_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkClassesJarSha256='0'*64))

    def test_wrong_primary_class_hash_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkGeckoEditableClassSha256=sdk.SDK_EDITABLE_SHA256))

    def test_wrong_manifest_digest_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkManifestSha256='0'*64))

    def test_wrong_runtime_receipt_digest_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkBuildReceiptSha256='0'*64))

    def test_wrong_tree_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sourceTree='0'*40))

    def test_wrong_source_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(sdkBuildSource='0'*40))

    def test_wrong_run_attempt_is_rejected(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(runAttempt='2'))

    def test_asset_requires_exact_field_set(self):
        self.rejects_identity(lambda value: value['sdkBuildIdentity'].update(nativeControlsEnabled=True))

    def test_runtime_receipt_requires_exact_field_set(self):
        value = dict(self.receipt, sdkBuildReceiptSha256='0'*64)
        with self.assertRaises(ValueError):
            sdk.validate_receipt(encoded(value), self.manifest, sdk.digest(self.materials[sdk.DERIVED_MANIFEST]), SOURCE, TREE)

    def test_runtime_receipt_cannot_claim_another_source(self):
        value = dict(self.receipt, sourceCommit='0'*40)
        with self.assertRaises(ValueError):
            sdk.validate_receipt(encoded(value), self.manifest, sdk.digest(self.materials[sdk.DERIVED_MANIFEST]), SOURCE, TREE)

    def test_runtime_receipt_cannot_replace_recipe(self):
        value = copy.deepcopy(self.receipt)
        value['sourceRecipe']['sha256'] = '0'*64
        with self.assertRaises(ValueError):
            sdk.validate_receipt(encoded(value), self.manifest, sdk.digest(self.materials[sdk.DERIVED_MANIFEST]), SOURCE, TREE)

    def test_nested_record_byte_count_requires_an_integer(self):
        value = copy.deepcopy(self.receipt)
        value['sourcePatch']['bytes'] = float(value['sourcePatch']['bytes'])
        with self.assertRaises(ValueError):
            sdk.validate_receipt(encoded(value), self.manifest, sdk.digest(self.materials[sdk.DERIVED_MANIFEST]), SOURCE, TREE)

    def test_edited_source_patch_bytes_are_rejected(self):
        self.materials[self.manifest['sourcePatch']['path']] += b'extra source modification'
        with self.assertRaises(ValueError):
            sdk.verify_sdk_identity(self.installed, SOURCE, TREE, self.raw, self.reader)

    def test_edited_recipe_bytes_are_rejected(self):
        self.materials[self.manifest['sourceRecipe']['path']] += b'extra compile option'
        with self.assertRaises(ValueError):
            sdk.verify_sdk_identity(self.installed, SOURCE, TREE, self.raw, self.reader)

    def test_allowlist_cannot_expand_to_inner_class(self):
        value = copy.deepcopy(self.manifest)
        value['changedClassEntries'].append('org/mozilla/geckoview/GeckoEditable$1.class')
        with self.assertRaises(ValueError):
            sdk.validate_manifest(encoded(value), SOURCE, self.reader)

    def test_native_changes_cannot_be_declared_acceptable(self):
        value = dict(self.manifest, allNativeAndResourceEntriesUnchanged=False)
        with self.assertRaises(ValueError):
            sdk.validate_manifest(encoded(value), SOURCE, self.reader)

    def test_unmodified_runtime_claim_is_rejected(self):
        for field in ('sdkAarModified', 'sdkClassTransformApplied', 'sourceCompileApplied'):
            with self.subTest(field=field), self.assertRaises(ValueError):
                sdk.validate_manifest(encoded(dict(self.manifest, **{field: False})), SOURCE, self.reader)

    def test_raw_receipt_bytes_not_only_parsed_object_are_bound(self):
        reformatted = (json.dumps(self.receipt, indent=2)+'\n').encode()
        with self.assertRaises(ValueError):
            sdk.verify_sdk_identity(self.installed, SOURCE, TREE, reformatted, self.reader)

    def test_duplicate_json_and_nonfinite_values_are_rejected(self):
        for value in ('{"schema":1,"schema":1}', '{"clock":NaN}', '{"clock":Infinity}'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sdk.strict_json(value)

    def test_report_engine_label_cannot_use_unmodified_label(self):
        self.report['engineVersion'] = 'GeckoView 157.0.1'
        with self.assertRaises(ValueError):
            sdk.verify_report_sdk(self.report, reader=self.reader)

    def test_ua_baseline_must_identify_same_actual_sdk(self):
        baseline = copy.deepcopy(self.report)
        baseline['sdkAarSha256'] = sdk.SDK_AAR_SHA256
        with self.assertRaises(ValueError):
            sdk.verify_report_sdk(self.report, baseline, self.reader)

    def test_apk_requires_both_unique_sdk_assets(self):
        for mode in ('missing-receipt', 'duplicate-identity'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/'synthetic.zip'
                with warnings.catch_warnings(), ZipFile(path,'w') as archive:
                    warnings.simplefilter('ignore', UserWarning)
                    archive.writestr(sdk.SDK_ASSET, encoded(self.asset))
                    if mode == 'duplicate-identity':
                        archive.writestr(sdk.SDK_ASSET, encoded(self.asset))
                        archive.writestr(sdk.SDK_RECEIPT_ASSET, self.raw)
                with ZipFile(path) as archive, self.assertRaises(ValueError):
                    sdk.sdk_from_apk(archive, SOURCE, TREE, self.reader)


def archive_bytes(entries):
    stream = io.BytesIO()
    with warnings.catch_warnings(), ZipFile(stream,'w') as archive:
        warnings.simplefilter('ignore', UserWarning)
        for name, value in entries:
            archive.writestr(name, value)
    return stream.getvalue()


class ExactArchiveDeltaTests(unittest.TestCase):
    def make(self, changed=None, extra=None, duplicate=False, native=b'unchanged native', remove=False):
        classes = [(sdk.EDITABLE_ENTRY, changed or b'original primary'),
                   ('org/mozilla/geckoview/GeckoEditable$1.class', b'original sibling'),
                   ('org/mozilla/geckoview/Other.class', b'original other')]
        if extra is not None:
            classes.append(extra)
        if remove:
            classes.pop()
        if duplicate:
            classes.append(classes[0])
        return archive_bytes([('classes.jar', archive_bytes(classes)), ('jni/x86_64/libxul.so', native), ('res/raw/unchanged', b'original resource')])

    def check_pair(self, derived):
        return sdk.verify_archive_delta(io.BytesIO(self.make()), io.BytesIO(derived))

    def test_only_primary_class_changes(self):
        self.assertEqual(self.check_pair(self.make(changed=b'derived primary')), [sdk.EDITABLE_ENTRY])

    def test_no_primary_change_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check_pair(self.make())

    def test_changed_inner_class_is_rejected(self):
        new = archive_bytes([('classes.jar', archive_bytes([(sdk.EDITABLE_ENTRY,b'derived primary'),
              ('org/mozilla/geckoview/GeckoEditable$1.class',b'changed sibling'),
              ('org/mozilla/geckoview/Other.class',b'original other')])),
              ('jni/x86_64/libxul.so',b'unchanged native'),('res/raw/unchanged',b'original resource')])
        with self.assertRaises(ValueError):
            self.check_pair(new)

    def test_added_observer_class_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check_pair(self.make(changed=b'derived primary', extra=('org/mozilla/geckoview/PocketGeckoInputTrace.class',b'observer')))

    def test_deleted_other_class_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check_pair(self.make(changed=b'derived primary', remove=True))

    def test_changed_native_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check_pair(self.make(changed=b'derived primary', native=b'changed native'))

    def test_duplicate_class_member_is_rejected(self):
        with self.assertRaises(ValueError):
            self.check_pair(self.make(changed=b'derived primary', duplicate=True))

    def test_duplicate_aar_member_is_rejected(self):
        data = archive_bytes([('classes.jar', b'x'), ('classes.jar', b'y')])
        with self.assertRaises(ValueError):
            self.check_pair(data)


if __name__ == '__main__':
    unittest.main()
