"""Execute the production PDF cover methods with a controlled native result callback."""

import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class GeckoPdfCoverTest(unittest.TestCase):
    def test_cover_proof_is_bound_to_rendered_document_and_grants_no_page_bridge(self):
        product = ROOT / 'app/src/main/java/local/pocketchat'
        source = (product / 'GeckoWebView.java').read_text(encoding='utf-8')
        member = runpy.run_path(str(ROOT / 'tests/loading-performance-host/run.py'))['member']
        methods = '\n'.join(member(source, needle) for needle in (
            'boolean hasVisibleDocument()', 'boolean hasVisibleContentForCover()',
            'private static final class PdfCoverProof', 'private static String pdfDocumentUrl(',
            'private boolean pdfCoverSession(', 'private void observePdfPaint(', 'private boolean navigationCurrent(',
        ))
        paint = member(source, 'public void onFirstContentfulPaint(GeckoSession s)')
        self.assertIn('observePdfPaint(s)', paint)
        self.assertEqual(source.count('observePdfPaint('), 2)
        self.assertIn('pdfCoverProofs.remove(s)', member(source, 'public void onLocationChange(GeckoSession s,'))
        self.assertIn('s.web.hasVisibleContentForCover()', (product / 'LoadingUi.java').read_text(encoding='utf-8'))

        java = os.environ.get('PROFILE_JAVA') or shutil.which('java')
        self.assertTrue(java, 'JDK required')
        java = Path(java).resolve()
        javac = java.with_name('javac' + java.suffix)
        with tempfile.TemporaryDirectory(prefix='gecko-pdf-cover-host-') as folder:
            path = Path(folder)
            host = path / 'PdfCoverHost.java'
            host.write_text(HOST.replace('/* PRODUCTION */', methods), encoding='utf-8')
            subprocess.run([str(javac), '-encoding', 'UTF-8', '-d', folder, str(host),
                            str(product / 'GeckoNavigationPolicy.java'), str(product / 'BrowserAddressPolicy.java')], check=True)
            subprocess.run([str(java), '-cp', folder, 'local.pocketchat.PdfCoverHost'], check=True)


HOST = r'''
package local.pocketchat;

import java.util.*;
import java.util.function.Consumer;

final class PdfCoverHost {
  static final String URL = "https://example.org/report";
  final Map<GeckoSession,PdfCoverProof> pdfCoverProofs = new IdentityHashMap<>();
  final Map<GeckoSession,String> locations = new IdentityHashMap<>();
  final Map<GeckoSession,Long> appearanceLoads = new IdentityHashMap<>();
  final Set<GeckoSession> usable = new HashSet<>(), crashed = new HashSet<>(), pendingLoads = new HashSet<>();
  final Owner owner = new Owner();
  GeckoSession current = new GeckoSession();
  boolean enabled = true, destroyed, failed, addonDisabled, ipRejected;

  static final class Owner {
    boolean deleted, navigationDispatched = true;
    long navigationEpoch = 1;
    int changes;
    void changed() { changes++; }
  }
  static final class GeckoSession {
    final Result result = new Result();
    boolean isOpen() { return true; }
    Result isPdfJs() { result.queries++; return result; }
  }
  static final class Result {
    int queries;
    Consumer<Boolean> success;
    Consumer<Throwable> failure;
    void accept(Consumer<Boolean> ok, Consumer<Throwable> error) { success = ok; failure = error; }
  }
  boolean ipNavigationFailed(GeckoSession session) { return ipRejected; }

  /* PRODUCTION */

  PdfCoverHost(String url) { locations.put(current, url); appearanceLoads.put(current, 1L); }
  static void check(boolean condition, String message) { if (!condition) throw new AssertionError(message); }

  public static void main(String[] args) {
    PdfCoverHost viewer = new PdfCoverHost(URL);
    check(!viewer.hasVisibleContentForCover(), "unpainted document remains covered");
    viewer.observePdfPaint(viewer.current);
    viewer.observePdfPaint(viewer.current);
    check(viewer.current.result.queries == 1 && !viewer.hasVisibleContentForCover(), "wait for native proof");
    viewer.current.result.success.accept(true);
    check(viewer.hasVisibleContentForCover() && !viewer.hasVisibleDocument() && viewer.owner.changes == 1,
          "verified PDF only lifts the cover");
    viewer.locations.put(viewer.current, URL + "#page=2");
    check(viewer.hasVisibleContentForCover(), "viewer page fragment does not hide the document");
    viewer.locations.put(viewer.current, URL + "?different=true");
    check(!viewer.hasVisibleContentForCover(), "proof cannot cross a different document URL");
    viewer.locations.put(viewer.current, URL);
    viewer.crashed.add(viewer.current);
    check(!viewer.hasVisibleContentForCover(), "crashed renderer cannot expose a blank surface");

    PdfCoverHost ordinary = new PdfCoverHost(URL + ".pdf");
    ordinary.observePdfPaint(ordinary.current);
    ordinary.current.result.success.accept(false);
    check(!ordinary.hasVisibleContentForCover() && ordinary.owner.changes == 0, "PDF-looking URL proves nothing");
    ordinary.usable.add(ordinary.current);
    check(ordinary.hasVisibleContentForCover(), "ordinary extension-ready page still controls the cover");

    for (int scenario = 0; scenario < 4; scenario++) {
      PdfCoverHost stale = new PdfCoverHost(URL);
      GeckoSession old = stale.current;
      stale.observePdfPaint(old);
      if (scenario == 0) stale.owner.navigationEpoch++;
      if (scenario == 1) stale.appearanceLoads.put(old, 2L);
      if (scenario == 2) stale.current = new GeckoSession();
      if (scenario == 3) stale.pendingLoads.add(old);
      old.result.success.accept(true);
      check(!stale.hasVisibleContentForCover() && stale.owner.changes == 0, "stale native callback " + scenario);
    }
    PdfCoverHost pending = new PdfCoverHost(URL);
    pending.pendingLoads.add(pending.current);
    pending.observePdfPaint(pending.current);
    check(pending.current.result.queries == 0, "uncommitted load cannot initiate a proof");
    pending.pendingLoads.clear();
    pending.observePdfPaint(pending.current);
    pending.current.result.failure.accept(new IllegalStateException());
    check(!pending.hasVisibleContentForCover(), "failed native check leaves cover unchanged");
  }
}
'''


if __name__ == '__main__':
    unittest.main()
