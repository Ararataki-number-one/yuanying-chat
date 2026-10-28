#!/usr/bin/env python3
"""Lossless metadata CSV controls, including actual Perfetto v54 fixtures."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('input_metadata_correlation',ROOT/'tools/gecko/correlate_input_trace.py')
M=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(M)
VALUES=[None,'','ordinary','"quote",comma','line1\nline2','back\\slash','[NULL]','NULL','é雪🙂','NUL\x00tail','CR\r\nLF']


def fixture_sql(encoded=True):
    rows=[]
    for index,value in enumerate(VALUES):
        text='NULL' if value is None else "CAST(X'"+value.encode('utf-8').hex().upper()+"' AS TEXT)"
        rows.append("SELECT %d AS id,'fixture-%d' AS name,'single' AS key_type,NULL AS int_value,%s AS str_value,NULL AS machine_id,0 AS trace_id"%(index,index,text))
    return 'WITH metadata AS ('+' UNION ALL '.join(rows)+') '+(M.METADATA_SELECT if encoded else 'SELECT * FROM metadata')+' ORDER BY id;'


def encoded_row(value='value'):
    return dict(id='1',name_utf8_hex='6E616D65',key_type_utf8_hex='73696E676C65',int_value='[NULL]',
                str_value_is_null='1' if value is None else '0',
                str_value_utf8_hex='' if value is None else value.encode('utf-8').hex().upper(),
                machine_id='[NULL]',trace_id='0')


def actual_fixture_proof(out):
    out.mkdir()
    trace=out/'empty-trace.json';trace.write_text('{"traceEvents":[]}\n')
    q=M.Queries(Path(M.TP_DEFAULT),trace,out)
    raw_rows=q.run('raw-complex-metadata',fixture_sql(False))
    encoded=q.run('hex-complex-metadata',fixture_sql(True),M.decode_metadata_rows)
    return q,encoded


class MetadataParserControls(unittest.TestCase):
    def test_eleven_strings_round_trip_without_null_coercion(self):
        for value in VALUES:
            with self.subTest(value=repr(value)):
                self.assertEqual(M.decode_metadata_rows([encoded_row(value)])[0]['str_value'],value)

    def test_seven_invalid_hex_null_or_utf8_forms_rejected(self):
        changes=[dict(str_value_utf8_hex='GG'),dict(str_value_utf8_hex='0'),dict(str_value_utf8_hex='aa'),
                 dict(str_value_utf8_hex='41 42'),dict(str_value_utf8_hex='FF'),
                 dict(str_value_is_null='2'),dict(str_value_is_null='1',str_value_utf8_hex='41')]
        for change in changes:
            with self.subTest(change=change),self.assertRaises((ValueError,UnicodeDecodeError)):
                M.decode_metadata_rows([dict(encoded_row(),**change)])

    def test_missing_or_extra_metadata_columns_rejected(self):
        row=encoded_row();row.pop('str_value_is_null')
        with self.assertRaises(ValueError): M.decode_metadata_rows([row])
        with self.assertRaises(ValueError): M.decode_metadata_rows([dict(encoded_row(),unexpected='x')])

    def test_invalid_numeric_metadata_rejected(self):
        with self.assertRaises(ValueError): M.decode_metadata_rows([dict(encoded_row(),int_value='NaN')])

    def test_original_strict_csv_column_guards_remain(self):
        for raw in [b'"x","x"\n1,2\n',b'"x"\n1,2\n',b'"x","y"\n1\n']:
            with self.subTest(raw=raw),self.assertRaises(ValueError): M.parse_csv(raw)

    def test_trace_resource_bound_accepts_exactly_256_mib(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'sparse.trace'
            with path.open('wb') as stream: stream.truncate(256*1024*1024)
            M.validate_trace_file(path)
            with path.open('r+b') as stream: stream.truncate(256*1024*1024+1)
            with self.assertRaises(ValueError): M.validate_trace_file(path)

    @unittest.skipUnless(Path(M.TP_DEFAULT).is_file(),'Pinned local v54 processor required')
    def test_actual_v54_raw_csv_failure_and_lossless_hex_query(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'proof';q,decoded=actual_fixture_proof(out)
            self.assertEqual(q.records[0]['returnCode'],0)
            self.assertEqual(q.records[0]['status'],'unavailable')
            self.assertEqual(q.records[0]['error'],'CSV column count differs')
            self.assertEqual(q.records[1]['status'],'queried')
            self.assertEqual([row['str_value'] for row in decoded],VALUES)
            self.assertEqual(q.records[0]['csvIdentity']['sha256'],M.sha(out/'raw-complex-metadata.csv'))
            self.assertEqual(q.records[1]['csvIdentity']['sha256'],M.sha(out/'hex-complex-metadata.csv'))

    @unittest.skipUnless(Path(M.TP_DEFAULT).is_file(),'Pinned local v54 processor required')
    def test_actual_v54_bad_encoded_value_remains_a_query_error(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td);trace=out/'empty.json';trace.write_text('{"traceEvents":[]}\n')
            query=M.Queries(Path(M.TP_DEFAULT),trace,out)
            sql="SELECT 1 AS id,'6E' AS name_utf8_hex,'73' AS key_type_utf8_hex,NULL AS int_value,0 AS str_value_is_null,'GG' AS str_value_utf8_hex,NULL AS machine_id,0 AS trace_id;"
            self.assertEqual(query.run('bad-hex',sql,M.decode_metadata_rows),[])
            self.assertEqual(query.records[0]['returnCode'],0)
            self.assertEqual(query.records[0]['status'],'unavailable')
            self.assertEqual(query.records[0]['error'],'Invalid uppercase byte-pair metadata hex')
            self.assertTrue((out/'bad-hex.csv').is_file())

    @unittest.skipUnless(Path(M.TP_DEFAULT).is_file(),'Pinned local v54 processor required')
    def test_actual_v54_helper_empty_trace_preserves_partial_status(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);trace=root/'empty.json';trace.write_text('{"traceEvents":[]}\n')
            receipt=root/'receipt.json';receipt.write_text(json.dumps(dict(driverPid=123,targetPidBefore='456',
                sourceCommit='a'*40,sourceTree='b'*40,buildIdentity=dict(runId='synthetic-run',runAttempt='1'),
                status='failed',error='synthetic fixed input failure',trace=dict(intervalMs=15,error='synthetic failure',
                    events=[dict(action=2,callStartUptimeMs=1000,callEndUptimeMs=1046,cleanup=False,sync=False)]))))
            args=argparse.Namespace(trace=trace,receipt=[receipt],processor=Path(M.TP_DEFAULT),out=root/'analysis',slow_call_ms=None)
            with contextlib.redirect_stdout(io.StringIO()): result=M.run(args)
            self.assertEqual(result['quality']['queryErrors'],[])
            self.assertTrue(result['quality']['partial'])
            self.assertFalse(result['uniqueCauseEstablished'])
            self.assertFalse(result['applicationAcceptance'])
            self.assertTrue(result['originalInputsUnchanged'])
            self.assertTrue((args.out/'trace-metadata.decoded.json').is_file())


if __name__=='__main__': unittest.main()
