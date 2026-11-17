"""Exact completion-only inverse for retained Java call-count history checks.

Current behavior hosts must compile the tracked fixture. This helper restores
only the retired four-call completion workload in an explicit history view;
it never supplies Java or JavaScript for execution.
"""
import hashlib

CURRENT_SHA256 = '6f805bf89e60e4f4bfef67ee2293839da0c848b347f84c28c0a6cc9db59ad63e'
HISTORICAL_SHA256 = '2d0ddc23e3bc64461c429d1a10d19ab5a9f199a9ee0dcf1b1ac70bba714e1746'
SIGNATURE = '  void completion(long serial){'
FOLLOWING = (
    '\n  // Only the origin is adapted for the loopback fixture. The production chooser,\n'
    '  // pending guard, SAF result and Gecko file preparation all run unchanged.\n'
    '  void desktopImage(long serial){desktopImage(serial,false);}'
)
HISTORICAL_COMPLETION = r'''  void completion(long serial){
    String html="<main><article data-turn='user'><div data-message-author-role='user' data-message-id='synthetic-user'>guest prompt</div></article><section><div data-message-author-role='assistant' data-message-id='synthetic-answer'><div class='markdown'>guest complete reply</div></div><button aria-label='Copy message'>Copy</button></section><textarea id='prompt-textarea'></textarea></main>";
    // Only this test copy accepts the strictly bounded loopback fixture. The
    // production driver continues to require the real HTTPS ChatGPT origin.
    String code=session.driver
      .replace("window !== window.top || location.origin !== 'https://chatgpt.com'", "window !== window.top || location.origin !== 'http://127.0.0.1:8765'")
      .replace("__ACTION__",JSONObject.quote("poll"))
      .replace("__ARG__",J.obj("userKey","id:synthetic-user","prompt","guest prompt","export",true).toString());
    session.web.evaluateJavascript("document.body.innerHTML="+JSONObject.quote(html),unused->{
      session.web.evaluateJavascript(code,raw->{
        JSONObject poll=J.parse(raw);
        boolean current=poll.optBoolean("terminal")&&poll.optBoolean("submitted")&&!poll.optBoolean("busy");
        String previous="document.querySelector('section button').remove();document.querySelector('main').insertAdjacentHTML('afterbegin','<section><div data-message-author-role=\"assistant\" data-message-id=\"prior\">old</div><button aria-label=\"Copy message\">Copy</button></section>');";
        session.web.evaluateJavascript(previous,v->{
          session.web.evaluateJavascript(code,later->{
            JSONObject old=J.parse(later);
            event(serial,"completion",J.obj("guestActionsRecognized",current,"priorActionsCannotComplete",!old.optBoolean("terminal"),"nestedMessageIdRecognized","id:synthetic-user".equals(poll.optString("userKey")),"reply",poll.optString("markdown"),"poll",poll));
          });
        });
      });
    });
  }'''


def restore_completion_for_history(source):
    """Accept one complete known completion method at its original boundary."""
    if type(source) is not str or source.count(SIGNATURE) != 1 or source.count(FOLLOWING) != 1:
        raise ValueError('Completion history requires unique original method boundaries')
    start = source.index(SIGNATURE)
    end = source.index(FOLLOWING)
    if start == 0 or source[start - 1] != '\n' or end <= start:
        raise ValueError('Completion method moved outside its original boundary')
    current = source[start:end]
    # FOLLOWING begins with the newline after the method's closing brace.
    if not current.endswith('\n  }'):
        raise ValueError('Completion history requires the complete closed method')
    digest = hashlib.sha256(current.encode('utf-8')).hexdigest()
    if digest not in (CURRENT_SHA256, HISTORICAL_SHA256):
        raise ValueError('Unknown completion method cannot alter the historical workload')
    if hashlib.sha256(HISTORICAL_COMPLETION.encode('utf-8')).hexdigest() != HISTORICAL_SHA256:
        raise ValueError('Pinned historical completion method changed')
    return source[:start] + HISTORICAL_COMPLETION + source[end:]
