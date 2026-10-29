#!/usr/bin/env python3
"""Real host SQLite exercises the exact display SELECT; no Android trace."""
import argparse,hashlib,json,re,sqlite3,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];PROD=ROOT/'app/src/main/java/local/pocketchat';HERE=Path(__file__).resolve().parent

def run():
 source=(PROD/'DownloadDisplaySnapshot.java').read_text();sql=re.search(r'static final String SQL="([^"\\]+)";',source).group(1)
 library=(PROD/'DownloadLibrary.java').read_text();schema=re.findall(r'db\.execSQL\("(CREATE (?:TABLE|INDEX) [^"]+)"\)',library);ddl=schema;assert len(ddl)==6
 checks=[];measurements=[]
 def check(name,passed):checks.append({'name':name,'pass':bool(passed)});assert passed,name
 def setup(db):
  for statement in ddl:db.execute(statement)
 def row(i):return {'id':'file'+str(i),'slot':i%8,'uri':'content://file/'+str(i),'state':'saved','time':1000+i,'name':'file.txt'}
 def insert(db,n):
  for i in range(n):
   value=row(i);encoded=json.dumps(value);db.execute('INSERT INTO files VALUES(?,?,?,?)',(value['slot'],value['uri'],encoded,value['time']));db.execute('INSERT INTO tasks VALUES(?,?,?,?)',(value['slot'],value['id'],encoded,value['time']))
  value={'id':'live','slot':0,'uri':'','state':'downloading','time':n+3000};db.execute('INSERT INTO tasks VALUES(?,?,?,?)',(0,'live',json.dumps(value),value['time']));db.commit()
 def prior(db):
  files=[json.loads(x[0])for x in db.execute('SELECT row FROM files ORDER BY time DESC')];tasks=[json.loads(x[0])for x in db.execute('SELECT row FROM tasks ORDER BY time DESC')];deleted=dict(db.execute('SELECT uri,time FROM deleted_files'));latest={}
  for x in db.execute('SELECT row FROM files ORDER BY time ASC'):
   value=json.loads(x[0]);latest[value['uri']]=value
  return files,tasks,deleted,latest
 def observed(db):
  files=[];tasks=[];deleted={};latest={};positions={}
  for kind,encoded,uri,stamp,position in db.execute(sql):
   if kind==1:deleted[uri]=stamp;continue
   value=json.loads(encoded)
   if kind==2:tasks.append(value);continue
   files.append(value)
   latest[value['uri']]=value
  return files,tasks,deleted,latest
 def norm(value):return json.dumps(value,sort_keys=True)
 def same(a,b):return sorted(map(norm,a[0]))==sorted(map(norm,b[0]))and sorted(map(norm,a[1]))==sorted(map(norm,b[1]))and a[2:]==b[2:]
 for n in [100,1000]:
  db=sqlite3.connect(':memory:');setup(db);insert(db,n);old=prior(db);fresh=observed(db);check(str(n)+' exact SELECT returns the same complete datasets/latest map',same(old,fresh));check(str(n)+' read does not start a write transaction',not db.in_transaction)
  # Same URI and DB timestamp in different slots, including divergent JSON time.
  for slot,name,json_time in [(0,'tie-first',21),(1,'tie-last',22)]:
   value={'id':name,'slot':slot,'uri':'content://tie','state':'saved','time':json_time};db.execute('INSERT INTO files VALUES(?,?,?,?)',(slot,value['uri'],json.dumps(value),7000))
  db.execute('INSERT INTO deleted_files VALUES(?,?)',('content://deleted',8000));db.commit();check(str(n)+' equal DB-time rowid tie agrees with original indexed ASC scan',same(prior(db),observed(db))and observed(db)[3]['content://tie']['id']=='tie-first')
  measurements.append({'savedRows':n,'oldStatementCount':4,'newStatementCount':1,'oldJsonRows':3*n+1,'newJsonRows':2*n+1,'sameDatasets':True});db.close()
 with tempfile.TemporaryDirectory(prefix='download38-sqlite-')as raw:
  path=Path(raw)/'fixture.sqlite';reader=sqlite3.connect(path,timeout=.2);reader.execute('PRAGMA journal_mode=WAL');setup(reader);insert(reader,1000);writer=sqlite3.connect(path,timeout=.2);cursor=reader.execute(sql);first=cursor.fetchone();writer.execute('DELETE FROM tasks');writer.commit();records=[first,*cursor.fetchall()];cursor.close();check('WAL writer commits while read statement cursor is open',writer.execute('SELECT count(*)FROM tasks').fetchone()[0]==0);check('One read statement retains original task rows through concurrent deletion',sum(record[0]==2 for record in records)==1001);check('Next statement observes the newer committed task table',not any(record[0]==2 for record in reader.execute(sql)));reader.close();writer.close()
 return {'status':'passed','checks':checks,'total':len(checks),'measurements':measurements,'sqliteVersion':sqlite3.sqlite_version,'sql':sql,'sqlSha256':hashlib.sha256(sql.encode()).hexdigest(),'productionSha256':hashlib.sha256(source.encode()).hexdigest(),'actualHostSqliteExecution':True,'actualAndroidExecution':False,'phonePerformanceMeasured':False,'scope':'Exact single SELECT against the actual schema4 DDL using Python host SQLite. Compares complete datasets/latest lookup with old indexed projections and exercises one open cursor during a WAL writer commit. Java production/pruning is covered separately against counted adapters; no Android scheduling/disk/frame conclusion.'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();value=run();a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':value['status'],'checks':value['total'],'output':str(a.output),'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}))
if __name__=='__main__':main()
