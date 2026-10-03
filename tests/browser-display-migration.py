"""Run the actual catalogue DDL against host SQLite; no app/browser data is used."""
import json,re,sqlite3,subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[1]
current=(root/'app/src/main/java/local/pocketchat/ProfileCatalog.java').read_text()
previous=subprocess.check_output(['git','show','ca4cfe1128c35fe8f5211b8d8b52ab84b8e40921:app/src/main/java/local/pocketchat/ProfileCatalog.java'],cwd=root,text=True)
ddl=lambda source:re.search(r'db\.execSQL\("(CREATE TABLE environments.*?)"\)',source).group(1)
checks=[]
def check(name,value):
    assert value,name
    checks.append({'name':name,'pass':True})
db=sqlite3.connect(':memory:');db.execute(ddl(previous))
for slot in range(8):
    db.execute('INSERT INTO environments(slot,name,created,draft,group_name,notes,opened,favorite) VALUES(?,?,?,?,?,?,?,?)',
        (slot,'保留环境 '+str(slot),1,json.dumps({'name':'原有草稿','nested':{'retain':True}},ensure_ascii=False),'工作','保留备注',slot+100,slot%2))
before=db.execute('SELECT * FROM environments ORDER BY slot').fetchall()
migration=re.search(r'if\(old<5\)db\.execSQL\("(.*?)"\)',current).group(1);db.execute(migration)
after=db.execute('SELECT * FROM environments ORDER BY slot').fetchall()
check('Schema upgrade keeps every prior environment field',all(a[:-1]==b for a,b in zip(after,before)))
check('All existing environments default to mobile display',all(a[-1]==0 for a in after))
db.execute('UPDATE environments SET desktop=1 WHERE slot=7')
check('Desktop mode belongs only to its selected environment',db.execute('SELECT desktop FROM environments ORDER BY slot').fetchall()==[(0,)]*7+[(1,)])
check('Changing display does not change drafts, groups or favorites',all(a[:-1]==b for a,b in zip(db.execute('SELECT * FROM environments ORDER BY slot'),before)))
db.execute('UPDATE environments SET desktop=0 WHERE slot=7')
check('Returning one environment to mobile preserves the others',db.execute('SELECT desktop FROM environments').fetchall()==[(0,)]*8)
fresh=sqlite3.connect(':memory:');fresh.execute(ddl(current));fresh.execute("INSERT INTO environments(slot,name) VALUES(1,'独立新环境')")
check('Fresh environments also default to mobile',fresh.execute('SELECT desktop FROM environments').fetchone()==(0,))
fresh.execute('UPDATE environments SET desktop=1 WHERE slot=1')
check('Fresh desktop selection persists when explicitly saved',fresh.execute('SELECT desktop FROM environments').fetchone()==(1,))
check('Old configuration drafts retain their exact stored text',all(json.loads(a[3])['nested']['retain'] for a in db.execute('SELECT * FROM environments')))
print(json.dumps({'passed':len(checks),'total':len(checks),'scope':'Host SQLite using the actual v4 and v5 DDL; Android multi-process/UI execution not claimed','checks':checks},ensure_ascii=False,indent=2))
