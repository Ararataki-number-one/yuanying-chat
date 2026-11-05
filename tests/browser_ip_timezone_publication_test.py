"""Real filesystem refusal paths; the device checker is an explicit modeled boundary."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ip_timezone_publication_under_test', ROOT / 'tools/browser/ip_timezone_publication.py')
publication = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publication)
SOURCE = 'a' * 40
EXPECTED = dict(sourceCommit=SOURCE, scope='Synthetic installed-reference boundary only')
RECEIPT = dict(sourceCommit=SOURCE, scope='Modeled selected-source checker; real filesystem only')


class IpTimezonePublicationTests(unittest.TestCase):
    def tool_fixture(self, root):
        source, destination = root / 'tool-source', root / 'tool-destination'
        (destination / 'tools/browser').mkdir(parents=True)
        values = {}
        for relative in publication.IP_RELEASE_TOOLS + publication.IP_SOURCE_ONLY_TOOLS:
            data = ('# Synthetic source-copy fixture: ' + relative + '\r\n').encode()
            selected = source / relative
            selected.parent.mkdir(parents=True, exist_ok=True)
            selected.write_bytes(data)
            values[relative] = data
        return source, destination, values

    def fixture(self, root):
        source, destination = root / 'source', root / 'destination'
        (source / publication.RAW_DIRECTORY).mkdir(parents=True)
        destination.mkdir()
        values = {publication.SUMMARY: b'{"syntheticBoundaryOnly":true,"kind":"summary"}\r\n'}
        for index, name in enumerate(publication.RAW_FILES):
            values[publication.RAW_DIRECTORY + '/' + name] = (json.dumps(dict(syntheticBoundaryOnly=True, index=index)) + '\r\n').encode()
        for relative, data in values.items():
            (source / relative).write_bytes(data)
        return source, destination, values

    def copy(self, source, destination, **kwargs):
        return publication.copy_gecko_ip_timezone_evidence(source, destination, SOURCE, EXPECTED, **kwargs)

    def test_current_checker_reference_and_exact_original_bytes_are_retained(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, destination, values = self.fixture(Path(tmp))
            reader = object()
            with patch.object(publication, 'verify', return_value=RECEIPT) as verify:
                result = self.copy(source, destination, reader=reader, required_regression=RECEIPT)
            verify.assert_called_once_with(source, SOURCE, EXPECTED, reader)
            self.assertEqual(result['regression'], RECEIPT)
            self.assertEqual(set(result['files']), set(values))
            self.assertEqual(len(result['files']), 14)
            self.assertEqual(publication.capture(destination), values)
            self.assertFalse(any(path.is_symlink() for path in destination.rglob('*')))

    def test_each_of_fourteen_missing_inputs_refuses_before_creating_output(self):
        for missing in (publication.SUMMARY, *(publication.RAW_DIRECTORY + '/' + name for name in publication.RAW_FILES)):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as tmp:
                source, destination, _ = self.fixture(Path(tmp))
                (source / missing).unlink()
                with patch.object(publication, 'verify') as verify:
                    with self.assertRaises((ValueError, OSError)):
                        self.copy(source, destination)
                    verify.assert_not_called()
                self.assertEqual(list(destination.iterdir()), [])

    def test_extra_keys_logs_nested_entries_and_non_json_objects_are_refused(self):
        for name, content in (('private.key', b'synthetic fixture text'), ('debug.log', b'log'), ('unexpected.json', b'{}')):
            with self.subTest(extra=name), tempfile.TemporaryDirectory() as tmp:
                source, destination, _ = self.fixture(Path(tmp))
                (source / publication.RAW_DIRECTORY / name).write_bytes(content)
                with patch.object(publication, 'verify') as verify:
                    with self.assertRaises(ValueError):
                        self.copy(source, destination)
                    verify.assert_not_called()
                self.assertEqual(list(destination.iterdir()), [])
        for raw in (b'[]', b'{"x":1,"x":2}', b'{broken', b'null'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                source, destination, _ = self.fixture(Path(tmp))
                (source / publication.RAW_DIRECTORY / publication.RAW_FILES[0]).write_bytes(raw)
                with self.assertRaises(ValueError):
                    self.copy(source, destination)
                self.assertEqual(list(destination.iterdir()), [])

    def test_input_file_directory_symlinks_and_named_pipe_cannot_be_read_as_evidence(self):
        for kind in ('summary-link', 'raw-link', 'raw-directory-link', 'source-directory-link', 'pipe'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source, destination, _ = self.fixture(root)
                if kind in ('summary-link', 'raw-link', 'pipe'):
                    selected = source / publication.SUMMARY if kind == 'summary-link' else source / publication.RAW_DIRECTORY / publication.RAW_FILES[0]
                    selected.unlink()
                    if kind == 'pipe':
                        os.mkfifo(selected)
                    else:
                        selected.symlink_to(root / 'not-an-evidence-file')
                else:
                    selected = source if kind == 'source-directory-link' else source / publication.RAW_DIRECTORY
                    moved = root / 'moved'
                    selected.rename(moved)
                    selected.symlink_to(moved, target_is_directory=True)
                with patch.object(publication, 'verify') as verify:
                    with self.assertRaises((ValueError, OSError)):
                        self.copy(source, destination)
                    verify.assert_not_called()
                self.assertEqual(list(destination.iterdir()), [])

    def test_sparse_oversize_inputs_are_rejected_without_loading_their_contents(self):
        for relative, limit in ((publication.SUMMARY, publication.MAX_SUMMARY_BYTES),
                                (publication.RAW_DIRECTORY + '/' + publication.RAW_FILES[0], publication.MAX_RAW_BYTES)):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                source, destination, _ = self.fixture(Path(tmp))
                with (source / relative).open('wb') as stream:
                    stream.truncate(limit + 1)
                with patch.object(publication, 'verify') as verify:
                    with self.assertRaises(ValueError):
                        self.copy(source, destination)
                    verify.assert_not_called()
                self.assertEqual(list(destination.iterdir()), [])

    def test_checker_refusal_changed_receipt_and_changed_bytes_prevent_all_output(self):
        for kind in ('checker-refused', 'receipt-changed', 'raw-changed'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                source, destination, _ = self.fixture(Path(tmp))
                def verify(*args):
                    if kind == 'checker-refused':
                        raise ValueError('Modeled actual checker refusal')
                    if kind == 'raw-changed':
                        (source / publication.RAW_DIRECTORY / publication.RAW_FILES[0]).write_bytes(b'{"changed":true}')
                    return dict(RECEIPT, changed=True) if kind == 'receipt-changed' else RECEIPT
                with patch.object(publication, 'verify', side_effect=verify):
                    with self.assertRaises(ValueError):
                        self.copy(source, destination, required_regression=RECEIPT)
                self.assertEqual(list(destination.iterdir()), [])

    def test_wrong_reference_and_dangling_or_existing_output_paths_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, destination, _ = self.fixture(Path(tmp))
            with patch.object(publication, 'verify') as verify:
                with self.assertRaises(ValueError):
                    publication.copy_gecko_ip_timezone_evidence(source, destination, SOURCE, dict(sourceCommit='b' * 40))
                verify.assert_not_called()
        for kind in ('summary', 'raw-directory', 'destination'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source, destination, _ = self.fixture(root)
                selected = destination / publication.SUMMARY if kind == 'summary' else destination / publication.RAW_DIRECTORY if kind == 'raw-directory' else destination
                if kind == 'destination':
                    destination.rmdir()
                selected.symlink_to(root / 'outside', target_is_directory=kind != 'summary')
                with patch.object(publication, 'verify', return_value=RECEIPT):
                    with self.assertRaises(ValueError):
                        self.copy(source, destination)
                self.assertFalse((root / 'outside').exists())

    def test_replaced_output_directory_never_receives_writes_through_its_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, destination, _ = self.fixture(root)
            outside = root / 'outside'
            outside.mkdir()
            actual_open = os.open
            moved = destination / 'retained-output'
            replaced = []
            def replace_after_directory_open(path, flags, *args, **kwargs):
                descriptor = actual_open(path, flags, *args, **kwargs)
                if path == publication.RAW_DIRECTORY and flags & os.O_DIRECTORY and kwargs.get('dir_fd') is not None and not replaced:
                    selected = destination / publication.RAW_DIRECTORY
                    selected.rename(moved)
                    selected.symlink_to(outside, target_is_directory=True)
                    replaced.append(True)
                return descriptor
            with patch.object(publication, 'verify', return_value=RECEIPT), patch.object(publication.os, 'open', side_effect=replace_after_directory_open):
                with self.assertRaises(ValueError):
                    self.copy(source, destination)
            self.assertEqual(replaced, [True])
            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual({path.name for path in moved.iterdir()}, set(publication.RAW_FILES))

    def test_exact_selected_source_dependencies_are_copied_without_mutating_identical_files(self):
        self.assertEqual(set(publication.IP_SOURCE_ONLY_TOOLS), {
            'tools/browser/check_gecko_ip_timezone_evidence.py',
            'tools/browser/run_gecko_ip_timezone_integration.py',
            'tools/browser/ip_timezone_fixture_server.py',
            'tools/browser/fingerprint_fixture_server.py',
            'tools/browser/newworker_fixture_server.py',
        })
        self.assertEqual(publication.IP_RELEASE_TOOLS, ('tools/browser/ip_timezone_publication.py',))
        with tempfile.TemporaryDirectory() as tmp:
            source, destination, values = self.tool_fixture(Path(tmp))
            requests = []
            def reader(commit, relative):
                requests.append((commit, relative))
                return values[relative]
            copied = publication.copy_gecko_ip_timezone_tools(source, destination, SOURCE, reader=reader)
            self.assertEqual(set(copied), set(values))
            self.assertEqual(requests, [(SOURCE, name) for name in publication.IP_SOURCE_ONLY_TOOLS])
            before = {name: ((destination / name).stat().st_ino, (destination / name).read_bytes()) for name in copied}
            publication.copy_gecko_ip_timezone_tools(source, destination, SOURCE, reader=reader)
            after = {name: ((destination / name).stat().st_ino, (destination / name).read_bytes()) for name in copied}
            self.assertEqual(before, after)
            self.assertEqual({name: raw for name, (_, raw) in after.items()}, values)

    def test_each_changed_source_only_dependency_refuses_before_copying_any_tool(self):
        for changed in publication.IP_SOURCE_ONLY_TOOLS:
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as tmp:
                source, destination, values = self.tool_fixture(Path(tmp))
                (source / changed).write_bytes(b'# changed after the tested source\n')
                with self.assertRaises(ValueError):
                    publication.copy_gecko_ip_timezone_tools(source, destination, SOURCE,
                                                            reader=lambda commit, name: values[name])
                self.assertEqual(list((destination / 'tools/browser').iterdir()), [])

    def test_source_tool_links_and_changed_or_linked_staged_dependencies_are_refused(self):
        for kind in ('source-link', 'staged-link', 'staged-changed', 'tool-directory-link'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source, destination, values = self.tool_fixture(root)
                selected_name = publication.IP_SOURCE_ONLY_TOOLS[0]
                outside = root / 'outside'
                outside.mkdir()
                if kind == 'source-link':
                    selected = source / selected_name
                    selected.unlink()
                    selected.symlink_to(outside / 'source.py')
                elif kind == 'tool-directory-link':
                    parent = destination / 'tools/browser'
                    parent.rmdir()
                    parent.symlink_to(outside, target_is_directory=True)
                elif kind == 'staged-link':
                    (destination / selected_name).symlink_to(outside / 'source.py')
                else:
                    (destination / selected_name).write_bytes(b'# unexpected staged dependency\n')
                with self.assertRaises((ValueError, OSError)):
                    publication.copy_gecko_ip_timezone_tools(source, destination, SOURCE,
                                                            reader=lambda commit, name: values[name])
                self.assertEqual(list(outside.iterdir()), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
