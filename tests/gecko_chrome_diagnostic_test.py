"""Guard selected-source diagnostic reuse; no counterfeit Android success."""
import ast
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'tests/gecko/run_chrome_collapse_diagnostic.py'
spec=importlib.util.spec_from_file_location('chrome_diagnostic',path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
source=(ROOT/'tests/gecko/run_ui_visuals.py').read_text()
original=ast.parse(source)

def named(tree,name):
    return next(n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name)
def calls(tree,name):
    return [n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id==name]
def normalized(node):return ast.dump(node,include_attributes=False)

class FocusedDiagnosticTest(unittest.TestCase):
    def test_unknown_scenario_rejected(self):
        with self.assertRaises(ValueError):module.selected_program(source,'retry')
    def test_cold_uses_the_exact_server_and_collapse_call(self):
        selected=module.selected_program(source,'cold')
        self.assertEqual(normalized(named(selected,'ReloadHttp')),normalized(named(original,'ReloadHttp')))
        self.assertEqual([normalized(n) for n in calls(selected,'run_chrome_collapse')],[normalized(n) for n in calls(original,'run_chrome_collapse')])
        self.assertEqual(len(calls(selected,'reload_check')),0)
    def test_reload_uses_all_exact_original_checks_and_taps(self):
        selected=module.selected_program(source,'after-reload')
        self.assertEqual([normalized(n) for n in calls(selected,'reload_check')],[normalized(n) for n in calls(original,'reload_check')])
        self.assertEqual(len(calls(selected,'reload_check')),8)
        self.assertEqual([normalized(n) for n in calls(selected,'reload_tap')],[normalized(n) for n in calls(original,'reload_tap')])
        self.assertEqual(len(calls(selected,'reload_tap')),3)
    def test_reload_functions_and_deadlines_unchanged(self):
        selected=module.selected_program(source,'after-reload')
        for name in ('chrome_event','focus','reload_check','reload_command','reload_tap','reload_ready'):
            self.assertEqual(normalized(named(selected,name)),normalized(named(original,name)))
    def test_both_programs_compile_without_execution(self):
        for scenario in ('cold','after-reload'):
            compile(module.selected_program(source,scenario),'selected-fixture','exec')
    def test_changed_source_shape_fails_closed(self):
        with self.assertRaises(ValueError):module.selected_program(source.replace('class ReloadHttp(', 'class OtherHttp('),'cold')
    def test_partial_reload_persisted_before_collapse(self):
        selected=module.selected_program(source,'after-reload')
        body=next(n for n in selected.body if isinstance(n,ast.Try)).body
        persist=next(i for i,n in enumerate(body) if 'ui-reload-confirmation.json' in ast.unparse(n))
        start=next(i for i,n in enumerate(body) if isinstance(n,ast.ImportFrom) and n.module=='run_chrome_collapse')
        self.assertLess(persist,start)
        self.assertEqual(len([n for n in body[:persist] if calls(n,'reload_check')]),8)
    def test_oracle_is_original_import_without_inlined_replacement(self):
        for scenario in ('cold','after-reload'):
            selected=module.selected_program(source,scenario)
            self.assertFalse(any(isinstance(n,ast.FunctionDef) and n.name=='run_chrome_collapse' for n in ast.walk(selected)))
            self.assertEqual(len([n for n in ast.walk(selected) if isinstance(n,ast.ImportFrom) and n.module=='run_chrome_collapse']),1)

if __name__=='__main__':unittest.main()
