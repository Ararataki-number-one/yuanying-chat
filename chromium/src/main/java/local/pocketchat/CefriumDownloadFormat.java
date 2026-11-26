package local.pocketchat;

import java.io.IOException;
import java.util.Locale;
import java.util.function.Function;

/** Final display metadata for a native download. It is never used as its staging path. */
final class CefriumDownloadFormat {
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
                                       String reportedMime, Function<String,String> typeForExtension,
                                       Function<String,String> extensionForType) throws IOException {
    String initial = usableName(offeredName);
    String last = usableName(reportedName);
    String suggested = initial;
    if (initial.isEmpty() || DownloadFileFormat.extension(initial).isEmpty()
        && !DownloadFileFormat.extension(last).isEmpty()) suggested = last;

    String type = concreteMime(reportedMime);
    if (type.isEmpty()) type = concreteMime(offeredMime);

    Document fromName = Document.fromName(suggested), fromMime = Document.fromMime(type);
    String extension = DownloadFileFormat.extension(suggested);
    String namedMime = DownloadFileFormat.mimeForName(suggested, "", typeForExtension);
    if (DownloadFileFormat.isHtml(type) && !DownloadFileFormat.GENERIC.equals(namedMime) && !DownloadFileFormat.isHtml(namedMime)
        || fromName != null && fromMime != null && (fromName == Document.PDF) != (fromMime == Document.PDF)) {
      throw new IOException("网页返回内容与下载文件格式不符，未保存");
    }
    if (fromName != null) type = fromName.mime;
    else if (fromMime != null) type = fromMime.mime;
    if (extension.isEmpty() && !type.isEmpty()) {
      String suffix = fromMime == null ? extensionForType.apply(type) : fromMime.suffix.substring(1);
      if (suffix != null) suggested = DownloadFileFormat.safeName(suggested) + "." + suffix;
    }
    String name = suggested.isEmpty() ? null : DownloadFileFormat.safeName(suggested);
    return new CefriumDownloadFormat(name, DownloadFileFormat.mimeForName(name, type, typeForExtension));
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
      case DownloadFileFormat.GENERIC:
      case "binary/octet-stream":
      case "application/force-download":
      case "application/x-download":
      case "application/download": return "";
      default: return type;
    }
  }

}
