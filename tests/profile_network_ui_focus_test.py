"""Keep the Android runner's popup handling narrow; never assume missing focus succeeded."""
import ast
import pathlib
import unittest
import xml.etree.ElementTree as ET


class NetworkUiFocusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = pathlib.Path(__file__).parent / "gecko/run_network_sources_ui.py"
        tree = ast.parse(path.read_text())
        functions = [item for item in tree.body if isinstance(item, ast.FunctionDef)
                     and item.name in ("matching", "field_focus_state")]
        namespace = {}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
        cls.classify = staticmethod(namespace["field_focus_state"])

    def state(self, nodes):
        return self.classify(ET.fromstring("<hierarchy>" + nodes + "</hierarchy>"), "出口名称")

    def test_exact_focused_field_required(self):
        self.assertEqual(self.state('<node class="android.widget.EditText" content-desc="出口名称" focused="true"/>'), "focused")
        for desc, focused in (("端口", "true"), ("出口名称", "false")):
            self.assertEqual(self.state(f'<node class="android.widget.EditText" content-desc="{desc}" focused="{focused}"/>'), "waiting")

    def test_framework_spelling_popup_is_identified_without_english_text(self):
        self.assertEqual(self.state('<node resource-id="android:id/suggestionWindowContainer"><node text="拼写建议"/></node>'), "spelling-popup")

    def test_other_dialogs_are_not_dismissed(self):
        self.assertEqual(self.state('<node resource-id="android:id/alertTitle" text="ADD TO DICTIONARY"/>'), "waiting")

    def test_duplicate_fields_do_not_count_as_focus(self):
        field = '<node class="android.widget.EditText" content-desc="出口名称" focused="true"/>'
        self.assertEqual(self.state(field + field), "waiting")


if __name__ == "__main__":
    unittest.main()
