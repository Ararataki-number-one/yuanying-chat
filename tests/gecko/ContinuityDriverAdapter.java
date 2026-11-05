package local.pocketchat;

/** Integration-only semantic-origin adapter; the production driver stays unchanged. */
final class ContinuityDriverAdapter {
  static final String SITE="window !== window.top || location.origin !== 'https://chatgpt.com'";
  static String adapt(String driver,String target){
    if(!target.matches("http://127\\.0\\.0\\.1:8765/browser-continuity\\?command=[1-9][0-9]*"))throw new IllegalArgumentException("Not the exact continuity fixture document");
    if(!driver.contains(SITE)||!driver.contains("__ACTION__")||!driver.contains("__ARG__"))throw new IllegalArgumentException("Production driver markers changed");
    // Compare JS values, rather than Android/host JSON spelling of escaped '/'.
    // A wrong expected URL is deliberately left for the original guard to reject.
    String arguments="(__ACTION__ === 'page-recover' && __ARG__ && __ARG__.expectedUrl === 'https://chatgpt.com/' ? Object.assign({}, __ARG__, {expectedUrl:'"+target+"'}) : __ARG__)";
    return driver.replace(SITE,"window !== window.top || location.origin !== 'http://127.0.0.1:8765'").replace("__ARG__",arguments);
  }
}
