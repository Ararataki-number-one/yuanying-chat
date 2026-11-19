package local.pocketchat;

import java.io.IOException;

public final class CefriumDownloadFormatTest {
  private static final String PDF = "application/pdf";
  private static final String WORD = "application/msword";
  private static final String DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

  private static void verify(String expectedName, String expectedMime, String firstName, String firstMime,
                             String finalName, String finalMime) throws Exception {
    CefriumDownloadFormat result = CefriumDownloadFormat.resolve(firstName, firstMime, finalName, finalMime);
    if (!java.util.Objects.equals(expectedName, result.name) || !expectedMime.equals(result.mime)) {
      throw new AssertionError("Unexpected file name or MIME: " + result.name + " / " + result.mime);
    }
  }

  private static void reject(String name, String type) throws Exception {
    try {
      CefriumDownloadFormat.resolve(name, "", name, type);
      throw new AssertionError("Conflicting metadata must not be published as " + name);
    } catch (IOException expected) {
      // The callback receives a visible file-format failure.
    }
  }

  public static void main(String[] args) throws Exception {
    verify("files.PDF", PDF, "files.PDF", "application/octet-stream", "payload.part", null);
    verify("report.docx", DOCX, "report.docx", "application/force-download", null, "binary/octet-stream");
    verify("letter.DOC", WORD, "letter.DOC", null, "payload.part", "application/download");
    verify("result.pdf", PDF, "result", "application/x-pdf", null, null);
    verify("文件.docx", DOCX, "", null, "payload.part", DOCX);
    verify("report.docx", DOCX, "download", "", "report.docx", WORD);
    verify("ä".repeat(125) + ".PDF", PDF, "ä".repeat(180) + ".PDF", "", null, null);
    verify("字".repeat(83) + ".DOCX", DOCX, null, null, "字".repeat(180) + ".DOCX", null);
    verify("x".repeat(155) + ".pdf", PDF, "x".repeat(155) + "😀tail.pdf", "", null, null);
    verify(".._.._report.docx", DOCX, "../../report.docx", "", "payload.part", "");
    verify("photo.jpeg", "image/jpeg", "photo.jpeg", "image/jpeg", null, "binary/octet-stream");
    verify(null, "application/octet-stream", null, null, "payload.part", "not a MIME");
    reject("attachment.pdf", "text/html; charset=utf-8");
    reject("attachment.docx", PDF);
    System.out.println("14 Cefrium file metadata cases passed");
  }
}
