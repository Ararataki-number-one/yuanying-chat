"""Deterministic host retirement and failed-JVM diagnostics; no Android execution."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / 'tests/saved-copy-host/run.py'
SPEC = importlib.util.spec_from_file_location('saved_copy_retirement_runner', RUNNER)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)

HOST = r'''
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class RetirementHost {
  static final class MainQueue {
    final ExecutorService executor=Executors.newSingleThreadExecutor();
    final AtomicInteger posts=new AtomicInteger();
    volatile CountDownLatch nextPost;
    boolean post(Runnable work){
      posts.incrementAndGet();executor.execute(work);
      CountDownLatch observed=nextPost;if(observed!=null){nextPost=null;observed.countDown();}
      return true;
    }
  }
  static final MainQueue main=new MainQueue();
  /* ACTUAL_UI */
  static final class Dialog {void dismiss(){throw new AssertionError("No dialog in retirement control");}}
  static final class Action {
    final ExecutorService worker;volatile boolean closed;long detailEpoch;Dialog detailDialog;
    Action(ExecutorService worker){this.worker=worker;}
    /* ACTUAL_CLOSE */
  }
  static final class Fixture {
    final Action action;Fixture(ExecutorService worker){action=new Action(worker);}
    /* ACTUAL_IDLE */
  }
  static class Delegating extends AbstractExecutorService {
    final ExecutorService real=Executors.newSingleThreadExecutor();
    public void execute(Runnable work){real.execute(work);}
    public void shutdown(){real.shutdown();}
    public List<Runnable> shutdownNow(){return real.shutdownNow();}
    public boolean isShutdown(){return real.isShutdown();}
    public boolean isTerminated(){return real.isTerminated();}
    public boolean awaitTermination(long timeout,TimeUnit unit)throws InterruptedException{return real.awaitTermination(timeout,unit);}
  }
  static final class Retiring extends Delegating {
    final CountDownLatch submitting=new CountDownLatch(1),closed=new CountDownLatch(1),uiFencePosted=new CountDownLatch(1);
    final CompletableFuture<Void> draining=new CompletableFuture<>();
    public void execute(Runnable fence){
      submitting.countDown();await(closed,"real close before submit");
      real.execute(fence);
    }
    public boolean awaitTermination(long timeout,TimeUnit unit)throws InterruptedException{
      draining.complete(null);boolean done=real.awaitTermination(timeout,unit);
      if(done)main.nextPost=uiFencePosted;
      return done;
    }
  }
  static void require(boolean pass,String message){if(!pass)throw new AssertionError(message);}
  static void await(CountDownLatch latch,String message){
    try{require(latch.await(5,TimeUnit.SECONDS),message);}
    catch(InterruptedException error){Thread.currentThread().interrupt();throw new AssertionError(message,error);}
  }
  static void retirementRace()throws Exception{
    Retiring worker=new Retiring();Fixture fixture=new Fixture(worker);
    ExecutorService caller=Executors.newSingleThreadExecutor();
    CountDownLatch copying=new CountDownLatch(1),releaseCopy=new CountDownLatch(1),
        uiBlocked=new CountDownLatch(1),releaseUi=new CountDownLatch(1);
    AtomicBoolean callbackApplied=new AtomicBoolean();
    try{
      worker.real.execute(()->{
        copying.countDown();await(worker.submitting,"fence attempts submission");
        try{ui(()->{fixture.action.close();main.post(()->{uiBlocked.countDown();await(releaseUi,"UI release");});return null;});}
        catch(Exception error){throw new CompletionException(error);}
        worker.closed.countDown();await(releaseCopy,"copy release");
        main.post(()->callbackApplied.set(true));
      });
      await(copying,"real copy task started");
      CompletableFuture<Void> idle=new CompletableFuture<>();
      caller.execute(()->{try{fixture.idle();idle.complete(null);}catch(Throwable error){idle.completeExceptionally(error);}});
      await(worker.closed,"real close completed");
      // Before the fix the captured false is followed by a real executor
      // rejection, so idle completes exceptionally instead of entering drain.
      CompletableFuture.anyOf(worker.draining,idle).get(5,TimeUnit.SECONDS);
      require(worker.draining.isDone(),"Retired worker must enter bounded drain");
      require(!idle.isDone(),"Retirement cannot finish before the real copy task");
      await(uiBlocked,"UI barrier started");releaseCopy.countDown();
      await(worker.uiFencePosted,"original UI fence posted after worker drain");
      require(!idle.isDone()&&!callbackApplied.get(),"UI fence waits behind the original completion callback");
      releaseUi.countDown();idle.get(5,TimeUnit.SECONDS);
      require(callbackApplied.get()&&worker.isTerminated(),"Both worker and UI completion are observed");
    }finally{releaseCopy.countDown();releaseUi.countDown();worker.shutdown();worker.real.awaitTermination(5,TimeUnit.SECONDS);caller.shutdownNow();}
  }
  static void alreadyRetired()throws Exception{
    Delegating worker=new Delegating();Fixture fixture=new Fixture(worker);int posts=main.posts.get();
    try{worker.shutdown();fixture.idle();require(worker.isTerminated()&&main.posts.get()==posts+1,"Already retired workers retain the UI fence");}
    finally{worker.shutdownNow();}
  }
  static void liveRejection()throws Exception{
    Delegating worker=new Delegating(){public void execute(Runnable work){throw new RejectedExecutionException("controlled-live-rejection");}};
    Fixture fixture=new Fixture(worker);int posts=main.posts.get();boolean rejected=false;
    try{
      try{fixture.idle();}catch(RejectedExecutionException error){rejected=error.getMessage().equals("controlled-live-rejection");}
      require(rejected&&!worker.isShutdown()&&main.posts.get()==posts,"A live executor rejection is never treated as retirement");
    }finally{worker.shutdownNow();}
  }
  static void workerFailure()throws Exception{
    Delegating worker=new Delegating(){public Future<?> submit(Runnable work){return real.submit(()->{throw new IllegalStateException("controlled-worker-failure");});}};
    Fixture fixture=new Fixture(worker);int posts=main.posts.get();boolean failed=false;
    try{
      try{fixture.idle();}catch(ExecutionException error){failed=error.getCause() instanceof IllegalStateException&&error.getCause().getMessage().equals("controlled-worker-failure");}
      require(failed&&main.posts.get()==posts,"A real failed worker Future must remain a failure");
    }finally{worker.shutdownNow();}
  }
  static void timeout(boolean retired)throws Exception{
    Delegating worker=new Delegating();Fixture fixture=new Fixture(worker);
    CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);int posts=main.posts.get();
    try{
      worker.real.execute(()->{entered.countDown();try{release.await();}catch(InterruptedException error){Thread.currentThread().interrupt();}});
      await(entered,"real blocked worker");if(retired)worker.shutdown();
      long started=System.nanoTime();boolean failed=false;
      try{fixture.idle();}
      catch(TimeoutException error){failed=!retired;}
      catch(AssertionError error){failed=retired&&"copy worker retirement".equals(error.getMessage());}
      long elapsed=TimeUnit.NANOSECONDS.toMillis(System.nanoTime()-started);
      require(failed&&elapsed>=4500&&main.posts.get()==posts,"Original five-second worker timeout must fail before UI fence");
    }finally{release.countDown();worker.shutdownNow();}
  }
  public static void main(String[] args)throws Exception{
    try{
      switch(args[0]){
        case "race":retirementRace();break;
        case "already-retired":alreadyRetired();break;
        case "live-rejection":liveRejection();break;
        case "worker-failure":workerFailure();break;
        case "live-timeout":timeout(false);break;
        case "retired-timeout":timeout(true);break;
        default:throw new AssertionError("Unknown control");
      }
      System.out.println("{\"mode\":\""+args[0]+"\",\"passed\":true}");
    }finally{main.executor.shutdownNow();}
  }
}
'''


class SavedCopyHostRetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        if not cls.java:
            raise RuntimeError('JDK 17+ is required for the actual retirement controls')
        cls.temp = tempfile.TemporaryDirectory(prefix='saved-copy-retirement-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.directory = Path(cls.temp.name)
        host = (ROOT / 'tests/saved-copy-host/CopyHost.java').read_text()
        production = (ROOT / 'app/src/main/java/local/pocketchat/SavedFileActions.java').read_text()
        cls.idle_source = runner.extract.member(host, 'void idle()')
        selected = HOST.replace('/* ACTUAL_IDLE */', cls.idle_source)
        selected = selected.replace('/* ACTUAL_UI */', runner.extract.member(host, 'static <T>T ui('))
        selected = selected.replace('/* ACTUAL_CLOSE */', runner.extract.member(production, 'void close()'))
        source = cls.directory / 'RetirementHost.java'
        source.write_text(selected)
        compiled = subprocess.run([cls.java, '-m', 'jdk.compiler/com.sun.tools.javac.Main',
                                   '-encoding', 'UTF-8', '-d', str(cls.directory), str(source)],
                                  text=True, capture_output=True, timeout=45)
        if compiled.returncode:
            raise AssertionError(compiled.stdout + compiled.stderr)

    def exercise(self, mode):
        completed = subprocess.run([self.java, '-cp', str(self.directory), 'RetirementHost', mode],
                                   text=True, capture_output=True, timeout=20)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(json.loads(completed.stdout), {'mode': mode, 'passed': True})

    def test_shutdown_between_inspection_and_submit_drains_real_worker(self):
        self.exercise('race')

    def test_already_retired_worker_still_observes_the_ui_fence(self):
        self.exercise('already-retired')

    def test_live_executor_rejection_is_not_masked(self):
        self.exercise('live-rejection')

    def test_failed_worker_future_is_not_masked(self):
        self.exercise('worker-failure')

    def test_live_and_retired_waits_keep_the_original_five_second_failures(self):
        self.assertEqual(self.idle_source.count('.get(5,TimeUnit.SECONDS)'), 1)
        self.assertEqual(self.idle_source.count('.awaitTermination(5,TimeUnit.SECONDS)'), 1)
        self.assertEqual(self.idle_source.count('ui(()->null);'), 1)
        for mode in ('live-timeout', 'retired-timeout'):
            with self.subTest(mode=mode):
                self.exercise(mode)


class SavedCopyHostDiagnosticsTests(unittest.TestCase):
    def test_invalid_output_preserves_exit_code_and_both_raw_streams(self):
        for code, stdout, stderr in ((1, '', 'RejectedExecutionException: controlled'),
                                     (0, 'non-JSON warning\n', 'controlled stderr\n'),
                                     (0, '[]', 'unexpected array')):
            with self.subTest(code=code, stdout=stdout), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'result.json'
                process = subprocess.CompletedProcess(['java'], code, stdout, stderr)
                with self.assertRaisesRegex(RuntimeError, 'Saved-copy JVM report') as raised:
                    runner.read_host_report(process, output)
                expected = {'exitCode': code, 'stdout': stdout, 'stderr': stderr}
                self.assertEqual(json.loads(output.with_suffix('.run.log').read_text()), expected)
                self.assertEqual(output.with_suffix('.stdout.txt').read_text(), stdout)
                self.assertEqual(output.with_suffix('.stderr.txt').read_text(), stderr)
                self.assertIn(json.dumps(expected, ensure_ascii=False), str(raised.exception))

    def test_nonzero_jvm_exit_cannot_leave_a_passing_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'result.json'
            value = runner.read_host_report(subprocess.CompletedProcess(
                ['java'], 3, '{"status":"passed","passed":51,"total":51}', 'controlled exit'), output)
            self.assertEqual(value['status'], 'failed')
            self.assertEqual(value['jvmExitCode'], 3)
            self.assertEqual(value['total'], 51)

    def test_success_and_original_failure_checks_remain_distinct(self):
        for status, code in (('passed', 0), ('failed', 1)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as temporary:
                original = {'status': status, 'passed': 51 if code == 0 else 50, 'total': 51,
                            'checks': [{'name': 'retained original check', 'pass': code == 0}]}
                value = runner.read_host_report(subprocess.CompletedProcess(
                    ['java'], code, json.dumps(original), ''), Path(temporary) / 'result.json')
                self.assertEqual(value, dict(original, jvmExitCode=code))
        self.assertIn("if run.returncode or report['status']!='passed':raise SystemExit(1)", RUNNER.read_text())


if __name__ == '__main__':
    unittest.main(verbosity=2)
