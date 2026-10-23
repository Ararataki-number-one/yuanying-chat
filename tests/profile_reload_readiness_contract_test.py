"""Run the exact visual runner readiness predicate on counterfeit metadata controls."""
import ast
import copy
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[1]
tree=ast.parse((ROOT/'tests/gecko/run_ui_visuals.py').read_text())
function=next(node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='reload_ready')
namespace={'re':re}
exec(compile(ast.Module(body=[function],type_ignores=[]),'run_ui_visuals.py:reload_ready','exec'),namespace)
ready=namespace['reload_ready']
RUN='reload-reloadStart-123456'


def metadata(path='/c/reload-A'):
    actual='http://127.0.0.1:8765'+path;virtual='https://chatgpt.com'+path
    return dict(visibleDocument=True,nativeSession=123,document='a'*32,
                nativeUrl='http://127.0.0.1:8765/c/reload-B',currentUrl='https://chatgpt.com/c/reload-B',path='/c/reload-B',
                documentReadyEvidence=dict(acceptedByProduction=True,fixtureRun=RUN,registeredRun=RUN,
                    topLevel=True,contentScript=True,nativeSession=123,currentSession=123,
                    rawMessage=dict(kind='documentReady',url=actual),senderUrl=actual,actualUrl=actual,
                    visibleUrl=virtual,normalizedMessage=dict(kind='documentReady',url=virtual),documentMarker='a'*32))


class ReloadReadinessContractTest(unittest.TestCase):
    def setUp(self):self.value=metadata()
    def reject(self,edit):
        value=copy.deepcopy(self.value);edit(value)
        self.assertIs(ready(value,'/c/reload-A',RUN),False)
    def evidence_reject(self,edit):self.reject(lambda value:edit(value['documentReadyEvidence']))

    def test_retained_spa_document_keeps_accepted_initial_ready_receipt(self):
        self.assertIs(ready(self.value,'/c/reload-A',RUN),True)

    def test_each_confirmed_reload_requires_its_new_document_receipt(self):
        self.assertIs(ready(metadata('/c/reload-B'),'/c/reload-B',RUN),True)
        self.assertIs(ready(self.value,'/c/reload-B',RUN),False)

    def test_previous_dom_only_ready_input_does_not_qualify(self):
        self.reject(lambda value:value.pop('documentReadyEvidence'))
        self.reject(lambda value:value.update(visibleDocument=False))

    def test_native_delegate_acceptance_and_visibility_are_strict_booleans(self):
        for invalid in (False,1,'true',None):
            self.reject(lambda value:value.update(visibleDocument=invalid))
            for key in ('acceptedByProduction','topLevel','contentScript'):
                self.evidence_reject(lambda evidence:evidence.update({key:invalid}))

    def test_run_binding_rejects_stale_or_invalid_nonce(self):
        for key in ('fixtureRun','registeredRun'):
            self.evidence_reject(lambda evidence:evidence.update({key:'reload-reloadStart-999'}))
        for invalid in ('',None,'reload-requestReload-123456'):
            value=copy.deepcopy(self.value);value['documentReadyEvidence'].update(fixtureRun=invalid,registeredRun=invalid)
            self.assertIs(ready(value,'/c/reload-A',invalid),False)

    def test_actual_session_identity_is_required_on_all_three_records(self):
        self.reject(lambda value:value.update(nativeSession=999))
        for key in ('nativeSession','currentSession'):
            self.evidence_reject(lambda evidence:evidence.update({key:999}))

    def test_boolean_cannot_fake_equal_integer_session_identity(self):
        for key in ('nativeSession','currentSession'):
            value=metadata();value['nativeSession']=1;value['documentReadyEvidence'].update(nativeSession=1,currentSession=1)
            value['documentReadyEvidence'][key]=True
            self.assertIs(ready(value,'/c/reload-A',RUN),False)

    def test_message_kind_must_be_actual_document_ready(self):
        self.evidence_reject(lambda evidence:evidence['rawMessage'].update(kind='result'))

    def test_actual_message_sender_and_current_document_must_match_exact_pair(self):
        self.evidence_reject(lambda evidence:evidence['rawMessage'].update(url='http://127.0.0.1:8765/c/reload-C'))
        for key in ('senderUrl','actualUrl','visibleUrl'):
            self.evidence_reject(lambda evidence:evidence.update({key:evidence[key]+'?foreign'}))

    def test_normalized_message_may_change_only_the_exact_url(self):
        self.evidence_reject(lambda evidence:evidence['normalizedMessage'].update(kind='ready'))
        self.evidence_reject(lambda evidence:evidence['normalizedMessage'].update(url='https://chatgpt.com/c/other'))
        self.evidence_reject(lambda evidence:evidence['normalizedMessage'].update(forged=True))

    def test_marker_must_match_actual_controlled_dom_and_be_nonempty(self):
        self.evidence_reject(lambda evidence:evidence.update(documentMarker='b'*32))
        for invalid in ('',None,'not-a-document'):
            value=copy.deepcopy(self.value);value['document']=invalid;value['documentReadyEvidence']['documentMarker']=invalid
            self.assertIs(ready(value,'/c/reload-A',RUN),False)

    def test_native_current_url_is_distinctly_checked_after_spa(self):
        for key in ('nativeUrl','currentUrl'):
            self.reject(lambda value:value.update({key:value[key]+'?foreign'}))

    def test_missing_or_wrong_raw_message_cannot_qualify(self):
        self.evidence_reject(lambda evidence:evidence.pop('rawMessage'))
        self.evidence_reject(lambda evidence:evidence.update(rawMessage=[]))
        self.reject(lambda value:value.update(documentReadyEvidence=[]))


if __name__=='__main__':unittest.main()
