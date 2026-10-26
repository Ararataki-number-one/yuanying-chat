#!/usr/bin/env python3
"""Execute production download DDL and migration branches in real host SQLite."""
import argparse, hashlib, importlib.util, json, pathlib, re, sqlite3, subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('download_member', ROOT / 'tests/download-resume-host/run.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=pathlib.Path)
    args = parser.parse_args()
    path = 'app/src/main/java/local/pocketchat/DownloadLibrary.java'
    text = (ROOT / path).read_text()
    version = int(re.search(r'super\(c,"saved-download-library.db",null,(\d+)\)', text).group(1))
    assert version == 4
    def ddl(name):
        body = adapter.member(text, name)
        return [json.loads('"' + raw + '"') for raw in re.findall(r'db\.execSQL\("((?:[^"\\]|\\.)*)"\)', body)]
    files = ddl('public void onCreate(')
    tasks = ddl('static void createTasks(')
    deleted = ddl('static void createDeleted(')
    indexes = ddl('static void createIndexes(')
    assert len(files) == len(tasks) == len(deleted) == 1 and len(indexes) == 3
    baseline_ref = 'da5004111eaf3e20322ca1fca3f756db82f44c90'
    baseline = subprocess.check_output(['git', 'show', baseline_ref + ':' + path], cwd=ROOT, text=True)
    for name in ['public void onCreate(', 'static void createTasks(', 'static void createDeleted(']:
        old_sql = re.findall(r'db\.execSQL\("((?:[^"\\]|\\.)*)"\)', adapter.member(baseline, name))
        current_sql = re.findall(r'db\.execSQL\("((?:[^"\\]|\\.)*)"\)', adapter.member(text, name))
        assert old_sql == current_sql, name
    branches = re.findall(r'if\(old<(\d+)\)(\w+)\(db\);', adapter.member(text, 'public void onUpgrade('))
    assert branches == [('2', 'createTasks'), ('3', 'createDeleted'), ('4', 'createIndexes')]
    methods = dict(createTasks=tasks, createDeleted=deleted, createIndexes=indexes)
    checks = []
    def check(name, passed):
        checks.append(dict(name=name, pass_=bool(passed)))
        assert passed, name
    def seed(db, old):
        db.executescript(files[0])
        if old >= 2:
            db.executescript(tasks[0])
        if old >= 3:
            db.executescript(deleted[0])
        db.executemany('INSERT INTO files VALUES (?,?,?,?)', [(i // 2500, 'content://fixture/' + str(i % 2500), json.dumps(dict(id=str(i), uri='content://fixture/' + str(i % 2500), time=i)), i) for i in range(5000)])
        if old >= 2:
            db.executemany('INSERT INTO tasks VALUES (?,?,?,?)', [(i // 2500, str(i), '{}', i) for i in range(5000)])
        if old >= 3:
            db.execute("INSERT INTO deleted_files VALUES ('content://deleted',123)")
        db.execute('PRAGMA user_version=' + str(old))
        db.commit()
    queries = {
        'indexed-uri': ('SELECT uri FROM files WHERE uri=?', ('content://fixture/100',)),
        'newest-uri-time': ('SELECT row FROM files WHERE uri=? ORDER BY time DESC LIMIT 1', ('content://fixture/100',)),
        'list-time': ('SELECT row FROM files ORDER BY time DESC', ()),
        'tasks-time': ('SELECT row FROM tasks ORDER BY time DESC', ()),
        'prune-time': ('SELECT row FROM files ORDER BY time ASC', ()),
    }
    plans = {}
    migration = []
    for old in [1, 2, 3]:
        db = sqlite3.connect(':memory:')
        seed(db, old)
        snapshot = list(db.execute('SELECT * FROM files ORDER BY slot,uri'))
        old_tasks = list(db.execute('SELECT * FROM tasks ORDER BY slot,id')) if old >= 2 else []
        old_deleted = list(db.execute('SELECT * FROM deleted_files ORDER BY uri')) if old >= 3 else []
        if old == 3:
            before_results = {name: list(db.execute(sql, params)) for name, (sql, params) in queries.items()}
            plans['before'] = {name: [row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + sql, params)] for name, (sql, params) in queries.items()}
        db.execute('BEGIN')
        for threshold, method in branches:
            if old < int(threshold):
                for sql in methods[method]:
                    db.execute(sql)
        db.execute('PRAGMA user_version=4')
        db.commit()
        check('v' + str(old) + ' to v4 preserves every file row', list(db.execute('SELECT * FROM files ORDER BY slot,uri')) == snapshot)
        check('v' + str(old) + ' to v4 preserves task rows', list(db.execute('SELECT * FROM tasks ORDER BY slot,id')) == old_tasks)
        check('v' + str(old) + ' to v4 preserves deletion tombstones', list(db.execute('SELECT * FROM deleted_files ORDER BY uri')) == old_deleted)
        check('v' + str(old) + ' to v4 retains same URI in distinct environments', db.execute("SELECT count(*) FROM files WHERE uri='content://fixture/100'").fetchone()[0] == 2)
        check('v' + str(old) + ' to v4 records schema4', db.execute('PRAGMA user_version').fetchone()[0] == 4)
        for table, names in [('files', ['files_uri_time', 'files_time']), ('tasks', ['tasks_time'])]:
            actual = {row[1]: row[2] for row in db.execute('PRAGMA index_list(' + table + ')')}
            check('v' + str(old) + ' ' + table + ' new indexes are nonunique', all(actual.get(name) == 0 for name in names))
        migration.append(dict(fromVersion=old, toVersion=4, fileRows=5000, taskRows=len(old_tasks), deletedRows=len(old_deleted)))
        if old == 3:
            plans['after'] = {name: [row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + sql, params)] for name, (sql, params) in queries.items()}
            for name, (sql, params) in queries.items():
                check(name + ' query results remain identical', list(db.execute(sql, params)) == before_results[name])
            check('URI lookup uses URI-first index', any('files_uri_time' in row and 'uri=?' in row for row in plans['after']['indexed-uri']))
            check('Newest URI lookup uses URI-time index without temporary sort', any('files_uri_time' in row for row in plans['after']['newest-uri-time']) and not any('TEMP B-TREE' in row for row in plans['after']['newest-uri-time']))
            for name, index in [('list-time', 'files_time'), ('tasks-time', 'tasks_time'), ('prune-time', 'files_time')]:
                check(name + ' uses time index without temporary sort', any(index in row for row in plans['after'][name]) and not any('TEMP B-TREE' in row for row in plans['after'][name]))
    fresh = sqlite3.connect(':memory:')
    for sql in files + tasks + deleted + indexes:
        fresh.execute(sql)
    check('Fresh schema creates all three new indexes', fresh.execute("SELECT count(*) FROM sqlite_master WHERE type='index' AND name IN ('files_uri_time','files_time','tasks_time')").fetchone()[0] == 3)
    index_definitions = {}
    for name, expected in [('files_uri_time', [('uri', 0), ('time', 1)]), ('files_time', [('time', 1)]), ('tasks_time', [('time', 1)])]:
        definition = list(fresh.execute('PRAGMA index_xinfo(' + name + ')'))
        index_definitions[name] = definition
        check(name + ' exact columns and descending order', [(row[2], row[3]) for row in definition if row[5]] == expected)
    rollback = sqlite3.connect(':memory:')
    seed(rollback, 3)
    rollback.execute('BEGIN')
    try:
        rollback.execute(indexes[0])
        rollback.execute('CREATE INDEX injected_invalid ON missing_table(uri)')
    except sqlite3.OperationalError:
        rollback.rollback()
    check('An interrupted transaction retains schema3 and no partial index', rollback.execute('PRAGMA user_version').fetchone()[0] == 3 and rollback.execute("SELECT count(*) FROM sqlite_master WHERE name='files_uri_time'").fetchone()[0] == 0 and rollback.execute('SELECT count(*) FROM files').fetchone()[0] == 5000)
    report = dict(status='passed', checks=[dict(name=row['name'], **{'pass': row['pass_']}) for row in checks], total=len(checks), sqliteVersion=sqlite3.sqlite_version, sourceCommit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), baselineSourceCommit=baseline_ref, baselineTableDDLUnchanged=True, sourceFile=path, sourceSha256=hashlib.sha256(text.encode()).hexdigest(), productionDDL=files+tasks+deleted+indexes, productionMigrationBranches=branches, migrations=migration, queryPlans=plans, indexDefinitions=index_definitions, actualSqliteExecution=True, actualAndroidExecution=False, phonePerformanceMeasured=False, statementCountImprovementClaim=False, scope='Production Java DDL strings and simple onUpgrade thresholds executed in real host SQLite; no Android SQLiteOpenHelper/framework or phone timing claim. Full-history serialization/prune/sync remains unchanged.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(status='passed', checks=len(checks), output=str(args.output))))

if __name__ == '__main__':
    main()
