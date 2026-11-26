#!/usr/bin/env python3
"""Run the exact download migration in separate JVMs with host SQLite and preference doubles."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
APP = ROOT / "app/src/main/java/local/pocketchat"
RECOVERY = ROOT / "tests/download-recovery-host/android"


def serve(database):
    with sqlite3.connect(database, isolation_level=None) as db:
        for line in sys.stdin:
            try:
                sql, args = json.loads(line)
                result = db.execute(sql, args)
                reply = [result.fetchall(), result.lastrowid, result.rowcount]
            except sqlite3.Error as error:
                reply = {"error": str(error)}
            print(json.dumps(reply), flush=True)


def run(java_home, jars):
    names = ("DownloadLibrary.java", "DownloadListPolicy.java", "DownloadMetadataValues.java",
             "DownloadTaskRevisions.java", "J.java")
    with tempfile.TemporaryDirectory(prefix="download-library-migration-") as raw:
        root = Path(raw)
        files = [HERE / "MigrationCases.java", *(APP / name for name in names)]
        for path in ("content/ContentValues.java", "net/Uri.java"):
            files.append(RECOVERY / path)

        def add(path, text):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
            files.append(target)

        preferences = (RECOVERY / "content/SharedPreferences.java").read_text()
        edits = {
            " public Editor edit()": ' public boolean getBoolean(String k,boolean d){return Boolean.parseBoolean(getString(k,String.valueOf(d)));}\n public Editor edit()',
            "public Editor putString": "public Editor putBoolean(String k,boolean v){return putString(k,String.valueOf(v));}public Editor putString",
        }
        for old, new in edits.items():
            assert preferences.count(old) == 1
            preferences = preferences.replace(old, new)
        add("android/content/SharedPreferences.java", preferences)
        add("android/content/Context.java", """package android.content;
import java.nio.file.*;
public final class Context {
  public final Path root; public final int slot;
  private final java.util.Map<String,SharedPreferences> stores=new java.util.HashMap<>();
  public Context(Path root,int slot){this.root=root;this.slot=slot;}
  public SharedPreferences getSharedPreferences(String name,int ignored){
    return stores.computeIfAbsent(name,k->{
      Path dir=root.resolve("slot-"+slot);
      try{Files.createDirectories(dir);}catch(java.io.IOException e){throw new IllegalStateException(e);}
      return new SharedPreferences(dir.resolve(name).toFile());
    });
  }
}""")
        add("android/database/Cursor.java", """package android.database;
import org.json.*;
public final class Cursor implements AutoCloseable {
  private final JSONArray rows; private int position=-1;
  public Cursor(JSONArray rows){this.rows=rows;}
  public boolean moveToNext(){return ++position<rows.length();}
  public boolean moveToFirst(){position=0;return rows.length()>0;}
  public String getString(int column){return rows.optJSONArray(position).optString(column);}
  public long getLong(int column){return rows.optJSONArray(position).optLong(column);}
  public void close(){}
}""")
        add("android/database/sqlite/SQLiteOpenHelper.java", """package android.database.sqlite;
import android.content.Context;
import java.nio.file.*;
public abstract class SQLiteOpenHelper implements AutoCloseable {
  private final Path path; private SQLiteDatabase database;
  protected SQLiteOpenHelper(Context context,String name,Object factory,int version){path=context.root.resolve(name);}
  public abstract void onCreate(SQLiteDatabase database);
  public abstract void onUpgrade(SQLiteDatabase database,int old,int next);
  public SQLiteDatabase getReadableDatabase(){return getWritableDatabase();}
  public SQLiteDatabase getWritableDatabase(){
    if(database==null){
      boolean fresh=!Files.exists(path);
      database=new SQLiteDatabase(path);
      if(fresh)onCreate(database);
    }
    return database;
  }
  public void close(){if(database!=null)database.close();}
}""")
        add("android/database/sqlite/SQLiteDatabase.java", """package android.database.sqlite;
import android.content.ContentValues;
import android.database.Cursor;
import java.io.*;
import java.nio.file.Path;
import java.util.*;
import org.json.*;
public final class SQLiteDatabase {
  public static final int CONFLICT_REPLACE=5;
  private final Process worker;
  private final BufferedReader input;
  private final BufferedWriter output;
  private boolean successful;
  public String failureKey="";
  public boolean reportFailure;
  SQLiteDatabase(Path database){
    try{
      worker=new ProcessBuilder(System.getProperty("python"),System.getProperty("bridge"),"--serve",database.toString()).redirectError(ProcessBuilder.Redirect.INHERIT).start();
      input=new BufferedReader(new InputStreamReader(worker.getInputStream()));
      output=new BufferedWriter(new OutputStreamWriter(worker.getOutputStream()));
    }catch(IOException e){throw new IllegalStateException(e);}
  }
  private JSONArray run(String statement,Object[] arguments){
    try{
      JSONArray args=arguments==null?new JSONArray():new JSONArray(Arrays.asList(arguments));
      output.write(new JSONArray().put(statement).put(args).toString());output.newLine();output.flush();
      return new JSONArray(input.readLine());
    }catch(IOException|JSONException e){throw new IllegalStateException("Controlled SQLite command failed: "+statement,e);}
  }
  public void execSQL(String statement){run(statement,null);}
  public void beginTransaction(){execSQL("BEGIN IMMEDIATE");successful=false;}
  public void setTransactionSuccessful(){successful=true;}
  public void endTransaction(){execSQL(successful?"COMMIT":"ROLLBACK");}
  public Cursor rawQuery(String statement,String[] arguments){return new Cursor(run(statement,arguments).optJSONArray(0));}
  public Cursor query(String table,String[] columns,String where,String[] args,String group,String having,String order){
    return query(table,columns,where,args,group,having,order,null);
  }
  public Cursor query(String table,String[] columns,String where,String[] args,String group,String having,String order,String limit){
    return rawQuery("SELECT "+String.join(",",columns)+" FROM "+table
        +(where==null?"":" WHERE "+where)+(order==null?"":" ORDER BY "+order)+(limit==null?"":" LIMIT "+limit),args);
  }
  public long insertWithOnConflict(String table,String empty,ContentValues values,int conflict){
    if(conflict!=CONFLICT_REPLACE)throw new AssertionError("Unexpected conflict mode");
    Object key=values.get(table.equals("tasks")?"id":"uri");
    if(failureKey.equals(key)){
      failureKey="";
      if(reportFailure)return -1;
      throw new IllegalStateException("Injected index write failure");
    }
    Set<String> columns=values.keySet();
    Object[] args=columns.stream().map(values::get).toArray();
    return run("INSERT OR REPLACE INTO "+table+" ("+String.join(",",columns)+") VALUES ("
        +String.join(",",Collections.nCopies(args.length,"?"))+")",args).optLong(1,-1);
  }
  public int delete(String table,String where,String[] args){return run("DELETE FROM "+table+" WHERE "+where,args).optInt(2);}
  public int update(String table,ContentValues values,String where,String[] args){throw new AssertionError("Unexpected update");}
  public void close(){
    try{output.close();input.close();if(worker.waitFor()!=0)throw new IllegalStateException("SQLite fixture exited abnormally");}
    catch(IOException|InterruptedException e){throw new IllegalStateException(e);}
  }
}""")
        for i, jar in enumerate(jars):
            classes = root / ("classes-" + str(i))
            state = root / ("state-" + str(i))
            state.mkdir()
            subprocess.run([java_home / "bin/javac", "--release", "8", "-encoding", "UTF-8",
                            "-cp", jar, "-d", classes, *files], check=True, timeout=30)
            launcher = [java_home / "bin/java", "-Dpython=" + sys.executable, "-Dbridge=" + str(Path(__file__).resolve()),
                        "-cp", os.pathsep.join((str(classes), str(jar))), "local.pocketchat.MigrationCases", state]
            for phase in ("fail", "restart"):
                subprocess.run([*launcher, phase], check=True, timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", type=Path)
    parser.add_argument("--java-home", type=Path)
    parser.add_argument("--json-jar", type=Path, action="append")
    arguments = parser.parse_args()
    if arguments.serve:
        serve(arguments.serve)
    elif arguments.java_home and arguments.json_jar:
        run(arguments.java_home, arguments.json_jar)
    else:
        parser.error("--java-home and --json-jar are required")
