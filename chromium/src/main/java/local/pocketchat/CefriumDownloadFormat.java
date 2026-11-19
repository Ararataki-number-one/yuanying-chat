package local.pocketchat;

import java.io.IOException;
import java.util.Locale;

/** Final display metadata for a native download. It is never used as its staging path. */
final class CefriumDownloadFormat {
  static final String GENERIC = "application/octet-stream";
  final String name;
  final String mime;

  private enum Document {
    PDF(".pdf", "application/pdf"),
    DOC(".doc", "application/msword"),
    DOCX(".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");

    final String suffix, mime;
    Document(String suffix, String mime) { this.suffix = suffix; this.mime = mime; }

    static Document fromName(String name) {
      String lower = name.toLowerCase(Locale.ROOT);
      for (Document document : values()) if (lower.endsWith(document.suffix)) return document;
      return null;
    }

    static Document fromMime(String mime) {
      if ("application/x-pdf".equals(mime)) return PDF;
      for (Document document : values()) if (document.mime.equals(mime)) return document;
      return null;
    }
  }

  private CefriumDownloadFormat(String name, String mime) {
    this.name = name;
    this.mime = mime;
  }

  static CefriumDownloadFormat resolve(String offeredName, String offeredMime, String reportedName,
                                       String reportedMime) throws IOException {
    String initial = usableName(offeredName);
    String last = usableName(reportedName);
    String suggested = initial;
    if (initial.isEmpty() || Document.fromName(initial) == null && Document.fromName(last) != null) suggested = last;

    String type = concreteMime(reportedMime);
    if (type.isEmpty()) type = concreteMime(offeredMime);

    Document fromName = Document.fromName(suggested), fromMime = Document.fromMime(type);
    if (fromName != null) {
      if ("text/html".equals(type) || "application/xhtml+xml".equals(type)
          || fromMime != null && (fromName == Document.PDF) != (fromMime == Document.PDF)) {
        throw new IOException("网页返回内容与下载文件格式不符，未保存");
      }
      String exactSuffix = suggested.substring(suggested.length() - fromName.suffix.length());
      String stem = suggested.substring(0, suggested.length() - exactSuffix.length());
      String outputMime = type.isEmpty() || fromMime != null ? fromName.mime : type;
      return new CefriumDownloadFormat(safeDocumentName(stem, exactSuffix), outputMime);
    }
    if (fromMime != null) return new CefriumDownloadFormat(safeDocumentName(suggested, fromMime.suffix), fromMime.mime);
    return new CefriumDownloadFormat(suggested.isEmpty() ? null : BrowserDownloadStore.safeName(suggested),
        type.isEmpty() ? GENERIC : type);
  }

  private static String usableName(String value) {
    String candidate = value == null ? "" : value.trim();
    return candidate.equals(".") || candidate.equals("..") || candidate.equalsIgnoreCase("payload.part")
        ? "" : candidate;
  }

  private static String concreteMime(String value) {
    String type = value == null ? "" : value.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
    if (!type.matches("[a-z0-9.+-]+/[a-z0-9.+-]+")) return "";
    switch (type) {
      case GENERIC:
      case "binary/octet-stream":
      case "application/force-download":
      case "application/x-download":
      case "application/download": return "";
      default: return type;
    }
  }

  private static String safeDocumentName(String stem, String suffix) {
    String safe = BrowserDownloadStore.safeName(stem);
    int characters = Math.min(safe.length(), 160 - suffix.length());
    int bytesLeft = 255 - suffix.length();
    int end = 0;
    while (end < characters) {
      int codePoint = safe.codePointAt(end);
      int width = Character.charCount(codePoint);
      int utf8 = codePoint < 0x80 ? 1 : codePoint < 0x800 ? 2 : width == 2 ? 4 : 3;
      if (end + width > characters || utf8 > bytesLeft) break;
      bytesLeft -= utf8;
      end += width;
    }
    return BrowserDownloadStore.safeName(safe.substring(0, end) + suffix);
  }
}
