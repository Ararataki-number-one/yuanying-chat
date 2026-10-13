package local.pocketchat;

/** Export the actual production script for read-only DOM behavior checks. */
public final class BrowserReadingFocusScript {
  public static void main(String[] args) {
    System.out.print(BrowserReadingPolicy.focusScript("https://chatgpt.com/c/reading"));
  }
}
