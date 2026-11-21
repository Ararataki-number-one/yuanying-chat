package local.pocketchat;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** Parses the diagnostic wire format, whose strings are ASCII keys and enums. */
final class AiDiagnosticJson {
  private static final int MAX_BYTES = 32 * 1024;
  private final String data;
  private int at;

  private AiDiagnosticJson(String data) { this.data = data; }

  static Map<?, ?> decode(byte[] bytes) throws IOException {
    if (bytes.length == 0 || bytes.length > MAX_BYTES) throw invalid();
    String text = StandardCharsets.UTF_8.newDecoder().decode(ByteBuffer.wrap(bytes)).toString();
    AiDiagnosticJson parser = new AiDiagnosticJson(text);
    Map<?, ?> result = object(parser.value(0));
    parser.whitespace();
    if (parser.at != text.length()) throw invalid();
    return result;
  }

  static Map<?, ?> object(Object value, String... keys) throws IOException {
    if (!(value instanceof Map)) throw invalid();
    Map<?, ?> map = (Map<?, ?>) value;
    if (keys.length != 0) {
      if (map.size() != keys.length) throw invalid();
      for (String key : keys) if (!map.containsKey(key)) throw invalid();
    }
    return map;
  }

  static List<?> array(Object value, int minimum, int maximum) throws IOException {
    if (!(value instanceof List)) throw invalid();
    List<?> items = (List<?>) value;
    if (items.size() < minimum || items.size() > maximum) throw invalid();
    return items;
  }

  static String text(Object value) throws IOException {
    if (!(value instanceof String)) throw invalid();
    return (String) value;
  }

  static IOException invalid() { return new IOException("网关诊断回复格式不受支持。"); }

  private Object value(int depth) throws IOException {
    whitespace();
    if (depth > 8 || at >= data.length()) throw invalid();
    char next = data.charAt(at);
    if (next == '{') return readObject(depth);
    if (next == '[') return readArray(depth);
    if (next == '"') return readText();
    if (next >= '0' && next <= '9') {
      at++;
      return next - '0';
    }
    throw invalid();
  }

  private Map<String, Object> readObject(int depth) throws IOException {
    at++;
    Map<String, Object> map = new LinkedHashMap<>();
    if (take('}')) return map;
    do {
      whitespace();
      String key = readText();
      if (map.size() == 16 || map.containsKey(key) || !take(':')) throw invalid();
      map.put(key, value(depth + 1));
    } while (take(','));
    if (!take('}')) throw invalid();
    return map;
  }

  private List<Object> readArray(int depth) throws IOException {
    at++;
    List<Object> list = new ArrayList<>();
    if (take(']')) return list;
    do {
      if (list.size() == 16) throw invalid();
      list.add(value(depth + 1));
    } while (take(','));
    if (!take(']')) throw invalid();
    return list;
  }

  private String readText() throws IOException {
    if (at >= data.length() || data.charAt(at++) != '"') throw invalid();
    int start = at;
    while (at < data.length() && data.charAt(at) != '"') {
      char ch = data.charAt(at++);
      if (!(ch >= 'A' && ch <= 'Z' || ch >= 'a' && ch <= 'z' || ch >= '0' && ch <= '9' || ch == '_')
          || at - start > 96) throw invalid();
    }
    if (at == data.length() || at == start) throw invalid();
    return data.substring(start, at++);
  }

  private boolean take(char expected) {
    whitespace();
    if (at >= data.length() || data.charAt(at) != expected) return false;
    at++;
    return true;
  }

  private void whitespace() {
    while (at < data.length()) {
      char ch = data.charAt(at);
      if (ch != ' ' && ch != '\t' && ch != '\r' && ch != '\n') return;
      at++;
    }
  }
}
