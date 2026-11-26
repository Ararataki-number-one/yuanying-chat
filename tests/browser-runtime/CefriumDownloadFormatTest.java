package local.pocketchat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;

public final class CefriumDownloadFormatTest {
  private static final String PDF = "application/pdf";
  private static final String WORD = "application/msword";
  private static final String DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

  private static String typeForExtension(String extension) {
    switch (extension) {
      case "pdf": return PDF;
      case "doc": return WORD;
      case "docx": return DOCX;
      case "csv": return "text/csv";
      case "html": return "text/html";
      case "jpeg": return "image/jpeg";
      case "zip": return "application/zip";
      default: return null;
    }
  }

  private static String extensionForType(String type) {
    return "text/csv".equals(type) ? "csv" : null;
  }

  private static void verify(String expectedName, String expectedMime, String firstName, String firstMime,
                             String finalName, String finalMime) throws Exception {
    CefriumDownloadFormat result = CefriumDownloadFormat.resolve(firstName, firstMime, finalName, finalMime,
        CefriumDownloadFormatTest::typeForExtension, CefriumDownloadFormatTest::extensionForType);
    if (!java.util.Objects.equals(expectedName, result.name) || !expectedMime.equals(result.mime)) {
      throw new AssertionError("Unexpected file name or MIME: " + result.name + " / " + result.mime);
    }
  }

  private static void reject(String name, String type) throws Exception {
    try {
      CefriumDownloadFormat.resolve(name, "", name, type,
          CefriumDownloadFormatTest::typeForExtension, CefriumDownloadFormatTest::extensionForType);
      throw new AssertionError("Conflicting metadata must not be published as " + name);
    } catch (IOException expected) {
      // The callback receives a visible file-format failure.
    }
  }

  private static void check(boolean actual, String detail) {
    if (!actual) throw new AssertionError(detail);
  }

  private static void sharedNames() {
    String longName = "报告😀".repeat(100) + ".xlsx";
    String numbered = DownloadFileFormat.numberedName(longName, 9999);
    check(numbered.endsWith(" (9999).xlsx"), "collision suffix must precede the extension");
    check(numbered.getBytes(StandardCharsets.UTF_8).length <= 240, "duplicate Unicode names must fit on disk");
    check(DownloadFileFormat.keepsExtension("report.PDF", "report (2).pdf"), "provider collision rename is safe");
    check(!DownloadFileFormat.keepsExtension("report.pdf", "report.pdf.bin"), "provider format substitution is rejected");
    check(DownloadFileFormat.dispositionName("attachment; filename=old.pdf; filename*=UTF-8''%E6%8A%A5%E5%91%8A+%20Q2.PDF")
        .equals("报告+ Q2.PDF"), "extended Unicode filename wins and a literal plus survives");
    check(DownloadFileFormat.dispositionName("attachment; filename=\"Q1; plan.pdf\"; filename*=UTF-8''broken%ZZ")
        .equals("Q1; plan.pdf"), "invalid extended filename falls back to quoted filename");
    check(DownloadFileFormat.dispositionName("attachment; note=\"fake; filename=bad.pdf\"; filename=real.pdf")
        .equals("real.pdf"), "quoted unrecognized parameters cannot supply a filename");
  }

  public static void main(String[] args) throws Exception {
    verify("files.PDF", PDF, "files.PDF", "application/octet-stream", "payload.part", null);
    verify("report.docx", DOCX, "report.docx", "application/force-download", null, "binary/octet-stream");
    verify("letter.DOC", WORD, "letter.DOC", null, "payload.part", "application/download");
    verify("result.pdf", PDF, "result", "application/x-pdf", null, null);
    verify("文件.docx", DOCX, "", null, "payload.part", DOCX);
    verify("report.docx", DOCX, "download", "", "report.docx", WORD);
    verify("ä".repeat(118) + ".PDF", PDF, "ä".repeat(180) + ".PDF", "", null, null);
    verify("字".repeat(78) + ".DOCX", DOCX, null, null, "字".repeat(180) + ".DOCX", null);
    verify("x".repeat(155) + ".pdf", PDF, "x".repeat(155) + "😀tail.pdf", "", null, null);
    verify(".._.._report.docx", DOCX, "../../report.docx", "", "payload.part", "");
    verify("photo.jpeg", "image/jpeg", "photo.jpeg", "image/jpeg", null, "binary/octet-stream");
    verify("表格.CSV", "text/csv", "表格.CSV", "text/plain", "payload.part", "application/octet-stream");
    verify("report.docx", DOCX, "report.docx", "application/zip", "payload.part", "application/zip");
    verify("result.csv", "text/csv", "result", "text/csv", null, null);
    verify("archive.ZIP", "application/zip", "archive.ZIP", "application/octet-stream", null, null);
    verify("saved.html", "text/html", "saved.html", "text/html", "payload.part", "text/html");
    verify(null, "application/octet-stream", null, null, "payload.part", "not a MIME");
    reject("attachment.pdf", "text/html; charset=utf-8");
    reject("attachment.docx", PDF);
    reject("attachment.csv", "text/html; charset=utf-8");
    sharedNames();
    System.out.println("20 Cefrium file metadata cases and 7 shared filename cases passed");
  }
}
