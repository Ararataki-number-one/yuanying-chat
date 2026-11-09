"""Execute production label hints and filename decoration, without Android claims."""
import base64
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / 'app/src/main/java/local/pocketchat'


class WorkspaceIconSemanticsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        if not cls.java:
            raise RuntimeError('Existing Java 17 compiler/runtime required')
        cls.temporary = tempfile.TemporaryDirectory(prefix='workspace-icon-semantics-')
        cls.addClassCleanup(cls.temporary.cleanup)
        work = Path(cls.temporary.name)
        loader = importlib.util.spec_from_file_location('icon_current_downloads', ROOT / 'tests/download-names-host/run.py')
        downloads = importlib.util.module_from_spec(loader)
        loader.loader.exec_module(downloads)
        style = PRODUCTION / 'DownloadWorkspaceStyle.java'
        current = style.read_text()
        methods = '\n'.join(downloads.member(current, needle) for needle in
                            ('static String savedGlyph(', 'static int savedColor('))
        # Only theme colors are boundaries. The actual filename methods execute
        # verbatim; country hints compile as complete production source files.
        host = work / 'WorkspaceIconHost.java'
        host.write_text('''package local.pocketchat;
import java.util.*;
import java.nio.charset.StandardCharsets;
final class WorkspaceIconHost {
  static String input(String value){return "<null>".equals(value)?null:value;}
  static void emit(String value){System.out.println("="+Base64.getEncoder().encodeToString(value.getBytes(StandardCharsets.UTF_8)));}
  public static void main(String[] arguments){
    String operation=arguments[0];
    if("common".equals(operation)){
      List<String> labels=new ArrayList<>();for(int i=1;i<arguments.length;i++)labels.add(input(arguments[i]));
      emit(NetworkCountryHint.commonCode(labels));return;
    }
    if("null-common".equals(operation)){emit(NetworkCountryHint.commonCode(null));return;}
    for(int i=1;i<arguments.length;i++){
      String value=input(arguments[i]);
      switch(operation){
        case "code":emit(NetworkCountryHint.code(value));break;
        case "pair":emit(NetworkCountryHint.code(value,input(arguments[++i])));break;
        case "country":emit(NetworkCountryHint.country(value));break;
        case "flag":emit(NetworkCountryHint.flag(value));break;
        case "file":emit(DownloadWorkspaceStyle.savedGlyph(value)+":"+DownloadWorkspaceStyle.savedColor(value));break;
        default:throw new IllegalArgumentException(operation);
      }
    }
  }
}
class DesignUi {static final int GREEN=1,CYAN=2;}
class ReferenceUi {static final int ORANGE=3;}
class DownloadWorkspaceStyle {
''' + methods + '\n}\n')
        sources = [PRODUCTION / 'NetworkCountryHint.java', PRODUCTION / 'NodeRegion.java', style]
        cls.source_hashes = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources}
        cls.classes = work / 'classes'
        compile_run = subprocess.run([cls.java, '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                                      '-encoding', 'UTF-8', '-d', str(cls.classes), str(host),
                                      str(sources[0]), str(sources[1])], capture_output=True, text=True, timeout=30)
        if compile_run.returncode:
            raise AssertionError(compile_run.stdout + compile_run.stderr)

    @classmethod
    def tearDownClass(cls):
        for path, expected in cls.source_hashes.items():
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise AssertionError('Production input changed during icon checks: ' + str(path))

    def query(self, operation, *values):
        result = subprocess.run([self.java, '-cp', str(self.classes), 'local.pocketchat.WorkspaceIconHost',
                                 operation, *('<null>' if value is None else value for value in values)],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertTrue(all(line.startswith('=') for line in lines), result.stdout)
        return [base64.b64decode(line[1:]).decode('utf-8') for line in lines]

    def test_explicit_codes_names_flags_and_role_prefixes(self):
        cases = [(None, ''), ('', ''), ('jp', 'JP'), ('日本', 'JP'),
                 ('Entry|🇯🇵 东京 01', 'JP'), ('Exit|Hong Kong 02', 'HK'),
                 ('中国香港', 'HK'), ('🇹🇼 台湾', 'TW'), ('DE Frankfurt 01', 'DE'),
                 ('🇸🇬 Singapore', 'SG'), ('United States', 'US')]
        self.assertEqual(self.query('code', *(label for label, _ in cases)), [code for _, code in cases])

    def test_addresses_unknown_and_conflicting_labels_stay_neutral(self):
        labels = ['https://jp.example.test', 'edge.jp', 'jp.example.com:443',
                  '192.0.2.1', '2001:db8::1', 'user@us.example.test',
                  '日本 https://example.test', 'intranet', 'music', '自动选择',
                  'JP SG', '日本 美国', '🇯🇵🇺🇸', '🇯🇵 Hong Kong', '🇺🇸 JP',
                  '🇯🇵 日本 新加坡', 'x' * 513]
        self.assertEqual(self.query('code', *labels), [''] * len(labels))

    def test_explicit_name_and_region_must_not_disagree(self):
        cases = [('东京 01', '新加坡', ''), ('东京 01', '未标注', 'JP'),
                 ('未知线路', 'Hong Kong', 'HK'), ('未知线路', '未标注', ''),
                 ('日本', 'JP', 'JP'), (None, 'US', 'US')]
        arguments = [value for name, region, _ in cases for value in (name, region)]
        self.assertEqual(self.query('pair', *arguments), [expected for _, _, expected in cases])

    def test_collection_requires_every_node_to_have_the_same_hint(self):
        for labels, expected in [([], ''), (['JP', '东京 02', '🇯🇵'], 'JP'),
                                 (['JP', 'US'], ''), (['JP', '未知'], ''),
                                 (['JP', None], ''), (['jp.example.test'], '')]:
            with self.subTest(labels=labels):
                self.assertEqual(self.query('common', *labels), [expected])
        self.assertEqual(self.query('null-common'), [''])

    def test_country_and_flag_outputs_require_valid_iso_codes(self):
        self.assertEqual(self.query('country', 'jp', 'HK', 'GB', 'ZZ', '', None),
                         ['日本', '中国香港', '英国', '', '', ''])
        self.assertEqual(self.query('flag', 'jp', 'HK', 'GB', 'ZZ', '', None),
                         ['🇯🇵', '🇭🇰', '🇬🇧', '', '', ''])

    def test_saved_file_decoration_uses_final_extension_and_preserves_color_roles(self):
        # 1=existing image green, 2=ordinary file cyan, 3=existing PDF orange.
        cases = [('report.PDF', 'file-pdf:3'), ('cover.PNG', 'image:1'),
                 ('notes.MD', 'file-text:2'), ('records.jsonl', 'file-text:2'),
                 ('backup.TAR.GZ', 'file-archive:2'), ('backup.7Z', 'file-archive:2'),
                 ('photo.png.backup', 'file:2'), ('report.pdf.exe', 'file:2'),
                 ('README', 'file:2'), ('archive.zip.txt', 'file-text:2')]
        self.assertEqual(self.query('file', *(name for name, _ in cases)), [expected for _, expected in cases])


if __name__ == '__main__':
    unittest.main()
