package local.pocketchat;

import java.io.ByteArrayOutputStream;
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.function.Function;

/** Filename and MIME rules shared by the browser engines and saved file destinations. */
final class DownloadFileFormat {
  static final String GENERIC = "application/octet-stream";
  private static final int MAX_CHARS = 160;
  private static final int MAX_BYTES = 240;

  private DownloadFileFormat() {}

  static String safeName(String value) {
    return safeName(value, "");
  }

  static String numberedName(String value, int number) {
    return safeName(value, number == 0 ? "" : " (" + number + ")");
  }

  private static String safeName(String value, String number) {
    String clean = value == null ? "" : value.replaceAll("[\\\\/:*?\"<>|\\p{Cntrl}]", "_").trim();
    while (clean.endsWith(".") && !clean.isEmpty()) clean = clean.substring(0, clean.length() - 1).trim();
    if (clean.isEmpty() || clean.equalsIgnoreCase("payload.part")) clean = "文件";
    String suffix = extension(clean).isEmpty() ? "" : clean.substring(clean.lastIndexOf('.'));
    String stem = clean.substring(0, clean.length() - suffix.length());
    int chars = MAX_CHARS - number.length() - suffix.length();
    int bytes = MAX_BYTES - number.length() - suffix.length();
    StringBuilder prefix = new StringBuilder();
    for (int offset = 0; offset < stem.length();) {
      int codePoint = stem.codePointAt(offset);
      int count = Character.charCount(codePoint);
      if (count == 1 && Character.isSurrogate(stem.charAt(offset))) codePoint = '_';
      int width = codePoint < 0x80 ? 1 : codePoint < 0x800 ? 2 : codePoint < 0x10000 ? 3 : 4;
      if (count > chars || width > bytes) break;
      prefix.appendCodePoint(codePoint);
      chars -= count;
      bytes -= width;
      offset += count;
    }
    String base = prefix.toString().trim();
    return (base.isEmpty() ? "文件" : base) + number + suffix;
  }

  static String extension(String name) {
    if (name == null) return "";
    int dot = name.lastIndexOf('.');
    if (dot <= 0) return "";
    String suffix = name.substring(dot + 1);
    return suffix.matches("[a-zA-Z0-9][a-zA-Z0-9_+-]{0,23}") ? suffix.toLowerCase(Locale.ROOT) : "";
  }

  static boolean keepsExtension(String requested, String actual) {
    String suffix = extension(requested);
    return actual != null && !actual.isEmpty() && (suffix.isEmpty() || suffix.equals(extension(actual)));
  }

  static String dispositionName(String header) {
    if (header == null || header.length() > 16384 || header.indexOf('\r') >= 0 || header.indexOf('\n') >= 0) return "";
    String ordinary = "";
    int start = header.indexOf(';');
    while (start >= 0 && start < header.length() - 1) {
      int end = parameterEnd(header, start + 1);
      String parameter = header.substring(start + 1, end).trim();
      int equals = parameter.indexOf('=');
      if (equals > 0) {
        String key = parameter.substring(0, equals).trim();
        String value = unquote(parameter.substring(equals + 1).trim());
        if (key.equalsIgnoreCase("filename*")) {
          String extended = extendedValue(value);
          if (usable(extended)) return safeName(extended);
        } else if (ordinary.isEmpty() && key.equalsIgnoreCase("filename") && usable(value)) {
          ordinary = safeName(value);
        }
      }
      start = end;
    }
    return ordinary;
  }

  private static int parameterEnd(String header, int start) {
    boolean quoted = false;
    for (int index = start; index < header.length(); index++) {
      char c = header.charAt(index);
      if (c == '\\' && quoted) index++;
      else if (c == '"') quoted = !quoted;
      else if (c == ';' && !quoted) return index;
    }
    return header.length();
  }

  private static String unquote(String value) {
    if (!value.startsWith("\"")) return value;
    if (value.length() < 2 || !value.endsWith("\"")) return "";
    StringBuilder unquoted = new StringBuilder();
    for (int index = 1; index < value.length() - 1; index++) {
      char c = value.charAt(index);
      if (c == '\\' && index + 1 < value.length() - 1) c = value.charAt(++index);
      unquoted.append(c);
    }
    return unquoted.toString();
  }

  private static boolean usable(String value) {
    String trimmed = value.trim();
    return !trimmed.isEmpty() && !trimmed.equals(".") && !trimmed.equals("..");
  }

  private static String extendedValue(String parameter) {
    int first = parameter.indexOf('\'');
    int second = first < 0 ? -1 : parameter.indexOf('\'', first + 1);
    if (second < 0) return "";
    String charsetName = parameter.substring(0, first);
    Charset charset;
    if (charsetName.equalsIgnoreCase("UTF-8")) charset = StandardCharsets.UTF_8;
    else if (charsetName.equalsIgnoreCase("ISO-8859-1")) charset = StandardCharsets.ISO_8859_1;
    else return "";
    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    for (int index = second + 1; index < parameter.length(); index++) {
      char c = parameter.charAt(index);
      if (c == '%') {
        if (index + 2 >= parameter.length()) return "";
        int high = Character.digit(parameter.charAt(++index), 16);
        int low = Character.digit(parameter.charAt(++index), 16);
        if (high < 0 || low < 0) return "";
        bytes.write(high * 16 + low);
      } else if (c > 32 && c < 127) {
        bytes.write(c);
      } else {
        return "";
      }
    }
    try {
      return charset.newDecoder().decode(ByteBuffer.wrap(bytes.toByteArray())).toString();
    } catch (CharacterCodingException malformed) {
      return "";
    }
  }

  static String mimeForName(String name, String reported, Function<String, String> resolveExtension) {
    String extension = extension(name);
    String known = standardMime(extension);
    if (known.isEmpty() && !extension.isEmpty()) known = mime(resolveExtension.apply(extension));
    if (!known.isEmpty() && !known.equals(GENERIC)) return known;
    String fallback = mime(reported);
    return fallback.isEmpty() ? GENERIC : fallback;
  }

  static boolean isHtml(String reported) {
    String type = mime(reported);
    return type.equals("text/html") || type.equals("application/xhtml+xml");
  }

  private static String mime(String value) {
    String type = value == null ? "" : value.split(";", 2)[0].trim().toLowerCase(Locale.ROOT);
    if (!type.matches("[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+")) return "";
    switch (type) {
      case "binary/octet-stream":
      case "application/force-download":
      case "application/x-download":
      case "application/download": return GENERIC;
      default: return type;
    }
  }

  private static String standardMime(String ext) {
    switch (ext) {
      case "pdf": return "application/pdf";
      case "doc": return "application/msword";
      case "docx": return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
      case "xls": return "application/vnd.ms-excel";
      case "xlsx": return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
      case "ppt": return "application/vnd.ms-powerpoint";
      case "pptx": return "application/vnd.openxmlformats-officedocument.presentationml.presentation";
      case "csv": return "text/csv";
      case "tsv": return "text/tab-separated-values";
      case "md": return "text/markdown";
      case "zip": return "application/zip";
      case "gz": return "application/gzip";
      default: return "";
    }
  }
}
