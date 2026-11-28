"""Keep the Android runner's popup handling narrow; never assume missing focus succeeded."""
import ast
import pathlib
import re
import unittest
import xml.etree.ElementTree as ET


class NetworkUiFocusTest(unittest.TestCase):
    package = "local.pocketchat.test"
    title = "编辑固定出口"
    field = ('<node package="local.pocketchat.test" class="android.widget.EditText" '
             'content-desc="出口名称，必填" focused="true" enabled="true" clickable="true" bounds="[20,100][300,148]"/>')

    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).parent / "gecko/run_network_sources_ui.py"
        tree = ast.parse(path.read_text())
        functions = [item for item in tree.body if isinstance(item, ast.FunctionDef)
                     and item.name in ("bounds", "form_inputs", "field_focus_state")]
        namespace = {"PACKAGE": cls.package, "re": re}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
        cls.classify = staticmethod(namespace["field_focus_state"])

    def state(self, nodes, title=None):
        title = title or self.title
        xml = (f'<hierarchy><node package="{self.package}"><node>'
               f'<node package="{self.package}" class="android.widget.TextView" text="{title}" content-desc="{title}"/>'
               f'<node package="{self.package}" class="android.widget.Button" content-desc="关闭{title}"/>'
               f'</node><node>{nodes}</node></node></hierarchy>')
        return self.classify(ET.fromstring(xml), "出口名称", self.title)

    def test_exact_focused_field_required(self):
        self.assertEqual(self.state(self.field), "focused")
        for old, new in (
            ("出口名称，必填", "端口，必填"),
            ("focused=\"true\"", "focused=\"false\""),
            ("EditText", "TextView"),
            (self.package, "other.app"),
            ("enabled=\"true\"", "enabled=\"false\""),
            ('bounds="[20,100][300,148]"', 'bounds="[20,100][300,100]"'),
        ):
            with self.subTest(new=new):
                self.assertEqual(self.state(self.field.replace(old, new)), "waiting")
        self.assertEqual(self.state(self.field, title="另一个弹窗"), "waiting")

    def test_framework_spelling_popup_is_identified_without_english_text(self):
        self.assertEqual(self.state('<node resource-id="android:id/suggestionWindowContainer"><node text="拼写建议"/></node>'), "spelling-popup")

    def test_other_dialogs_are_not_dismissed(self):
        self.assertEqual(self.state('<node resource-id="android:id/alertTitle" text="ADD TO DICTIONARY"/>'), "waiting")

    def test_duplicate_fields_do_not_count_as_focus(self):
        self.assertEqual(self.state(self.field + self.field), "waiting")


if __name__ == "__main__":
    unittest.main()
