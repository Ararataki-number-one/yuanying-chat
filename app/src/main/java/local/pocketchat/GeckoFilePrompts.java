package local.pocketchat;

import android.content.Intent;
import android.net.Uri;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import java.io.IOException;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.atomic.AtomicBoolean;
import org.mozilla.geckoview.GeckoResult;
import org.mozilla.geckoview.GeckoSession;

/** Owns Gecko's file prompt from Android chooser launch until renderer confirmation or dismissal. */
final class GeckoFilePrompts implements GeckoSession.PromptDelegate {
  private static final String PREPARING = "准备附件…";
  private final GeckoWebView web;

  GeckoFilePrompts(GeckoWebView web) { this.web = web; }

  @Override public GeckoResult<PromptResponse> onFilePrompt(GeckoSession session, FilePrompt prompt) {
    WebChromeClient chrome = web.chrome;
    if (web.destroyed || chrome == null || session != web.current) return GeckoResult.fromValue(prompt.dismiss());
    Request request = new Request(session, prompt, chrome);
    request.open();
    return request.result;
  }

  private static WebChromeClient.FileChooserParams params(FilePrompt prompt) {
    return new WebChromeClient.FileChooserParams() {
      @Override public int getMode() { return prompt.type == FilePrompt.Type.MULTIPLE ? MODE_OPEN_MULTIPLE : MODE_OPEN; }
      @Override public String[] getAcceptTypes() { return prompt.mimeTypes; }
      @Override public boolean isCaptureEnabled() { return false; }
      @Override public CharSequence getTitle() { return prompt.title; }
      @Override public String getFilenameHint() { return ""; }
      @Override public Intent createIntent() {
        return new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("*/*").addCategory(Intent.CATEGORY_OPENABLE);
      }
    };
  }

  private final class Request {
    final ChatSession owner = web.owner;
    final long navigation = owner.navigationEpoch;
    final GeckoSession session;
    final FilePrompt prompt;
    final WebChromeClient chrome;
    final GeckoPhotoPermission photo;
    final GeckoResult<PromptResponse> result = new GeckoResult<>();
    final ValueCallback<Uri[]> selection = this::selected;
    final AtomicBoolean receivedSelection = new AtomicBoolean();
    volatile boolean cancelled;
    String previousStatus;
    AttachmentIssue previousIssue;

    Request(GeckoSession session, FilePrompt prompt, WebChromeClient chrome) {
      this.session = session;
      this.prompt = prompt;
      this.chrome = chrome;
      this.photo = new GeckoPhotoPermission(web, session);
    }

    void open() {
      owner.resourceFileWork(true, true);
      prompt.setDelegate(new PromptInstanceDelegate() {
        @Override public void onPromptDismiss(BasePrompt ignored) {
          cancelled = true;
          photo.cancel();
          if (chrome instanceof Attachments.Chrome) ((Attachments.Chrome)chrome).dismissFilePrompt(selection);
          selection.onReceiveValue(null);
          dismiss();
        }
      });
      photo.capture(() -> {
        if (!photo.current() || cancelled || prompt.isComplete()) { selected(null); return; }
        try {
          if (!chrome.onShowFileChooser(null, selection, params(prompt))) selected(null);
        } catch (RuntimeException error) {
          selected(null);
          owner.setAttachmentIssue(AttachmentIssue.PICKER_FAILED);
        }
      });
    }

    void dismiss() {
      if (!prompt.isComplete()) result.complete(prompt.dismiss());
    }

    void selected(Uri[] uris) {
      if (!receivedSelection.compareAndSet(false, true)) return;
      if (uris == null || uris.length == 0 || web.destroyed || cancelled || prompt.isComplete()) {
        photo.cancel();
        owner.resourceFileWork(true, false);
        dismiss();
        return;
      }
      // Acquire preparation ownership before releasing the picker so Gecko stays active across the handoff.
      owner.resourceFileWork(false, true);
      owner.resourceFileWork(true, false);
      previousStatus = owner.status;
      previousIssue = owner.attachmentIssue;
      owner.setStatus(PREPARING);
      try {
        web.uploadWorker.execute(() -> prepare(uris));
      } catch (RejectedExecutionException error) {
        preparationFailed("附件读取已结束，请重新打开文件选择器");
      }
    }

    void prepare(Uri[] uris) {
      try {
        GeckoUploadFiles.Selection files = GeckoUploadFiles.prepare(owner.context, uris, () -> cancelled);
        owner.handler.post(() -> photo.allow(files.containsImage, issue -> handOff(files, issue)));
      } catch (IOException error) {
        if (error instanceof GeckoUploadFiles.Cancelled) web.lastUploadCleanup = ((GeckoUploadFiles.Cancelled)error).cleanup;
        owner.handler.post(() -> preparationFailed(error.getMessage()));
      }
    }

    void preparationFailed(String message) {
      photo.cancel();
      finishPreparation();
      dismiss();
      if (!web.destroyed && !cancelled) owner.setStatus(message);
    }

    void handOff(GeckoUploadFiles.Selection files, AttachmentIssue issue) {
      try {
        if (issue != null || web.destroyed || cancelled || session != web.current || !session.isOpen()
            || navigation != owner.navigationEpoch || prompt.isComplete()) {
          photo.cancel();
          web.retireUnhandedUpload(files);
          dismiss();
          if (issue != null && !web.destroyed && !cancelled) owner.setAttachmentIssue(issue);
          return;
        }
        PromptResponse response;
        try {
          response = prompt.confirm(owner.context, files.files);
        } catch (RuntimeException error) {
          photo.cancel();
          web.retireUnhandedUpload(files);
          dismiss();
          owner.setStatus("附件未能交给网页，请重新选择");
          return;
        }
        web.uploadFiles.add(files);
        owner.resourceFilesPrepared(files.files, navigation);
        photo.handedOff();
        result.complete(response);
      } finally {
        finishPreparation();
      }
    }

    void finishPreparation() {
      owner.resourceFileWork(false, false);
      if (web.destroyed || owner.resourceFilePreparations != 0) return;
      if (!PREPARING.equals(owner.status)) owner.changed();
      else if (previousIssue != null) owner.setAttachmentIssue(previousIssue);
      else owner.setStatus(PREPARING.equals(previousStatus) ? "" : previousStatus);
    }
  }
}
