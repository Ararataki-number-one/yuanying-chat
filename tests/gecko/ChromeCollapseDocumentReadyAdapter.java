package local.pocketchat;

/** Exact test-only pair for the virtual ChatGPT origin used by this local fixture. */
final class ChromeCollapseDocumentReadyAdapter {
  static final String ACTUAL="http://127.0.0.1:8765/c/reload-collapse";
  static final String VIRTUAL="https://chatgpt.com/c/reload-collapse";
  static boolean maps(String kind,String incoming,String actual,String sender,String visible,boolean current,boolean topLevel,boolean contentScript){
    return "documentReady".equals(kind)&&ACTUAL.equals(incoming)&&ACTUAL.equals(actual)&&ACTUAL.equals(sender)&&VIRTUAL.equals(visible)&&current&&topLevel&&contentScript;
  }
}
