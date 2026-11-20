package local.pocketchat.chromiumfixture;

import android.app.Activity;
import android.app.UiAutomation;
import android.content.ContentValues;
import android.content.Context;
import android.graphics.Paint;
import android.graphics.pdf.PdfDocument;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.view.accessibility.AccessibilityNodeInfo;
import com.cefrium.CefriumBrowser;
import com.cefrium.CefriumProfile;
import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayDeque;
import java.util.Arrays;
import java.util.Locale;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import static local.pocketchat.chromiumfixture.RouteFixture.field;
import static local.pocketchat.chromiumfixture.RouteFixture.invoke;
import static local.pocketchat.chromiumfixture.RouteFixture.require;

/** Synthetic document and profile checks using the real app browser on a disposable x86_64 guest. */
final class FilesAndProfilesFixture {
    private static final String HTML = "text/html; charset=utf-8";
    private static final String COOKIE = "pocketchat_fixture_session";
    private static final String STORE = "pocketchat-fixture-local";
    private final RouteFixture fixture;
    private final Context target;
    private final String nonce;

    FilesAndProfilesFixture(RouteFixture fixture, Context target, String nonce) {
        this.fixture = fixture;
        this.target = target;
        this.nonce = nonce;
    }

    static boolean supports(String mode) {
        return "files".equals(mode) || "profile-seed".equals(mode) || "profile-read".equals(mode);
    }

    void exercise(String mode, Bundle result) throws Exception {
        result.putString("fixtureMode", mode);
        result.putInt("fixturePid", android.os.Process.myPid());
        if ("files".equals(mode)) files(result);
        else profiles("profile-seed".equals(mode), result);
        result.putBoolean("realChatGptAcceptance", false);
    }

    private Activity open(LoopbackProxy proxy, String path, int slot, boolean create) throws Exception {
        String url = proxy.origin() + path;
        fixture.onMain(() -> {
            ClassLoader loader = target.getClassLoader();
            Class<?> catalogType = loader.loadClass("local.pocketchat.ProfileCatalog");
            Object catalog = invoke(catalogType, null, "get", new Class<?>[]{Context.class}, target);
            Class<?> profiles = loader.loadClass("local.pocketchat.Profiles");
            if (slot != 0 && create) invoke(profiles, null, "prepare",
                    new Class<?>[]{Context.class, int.class, boolean.class}, target, slot, false);
            invoke(catalogType, catalog, "identity", new Class<?>[]{int.class}, slot);
            Context environment = (Context)invoke(profiles, null,
                    "context", new Class<?>[]{Context.class, int.class}, target, slot);
            fixture.selectEnvironment(environment, proxy.endpoint(), false, url);
            return null;
        });
        Activity activity = fixture.launchEnvironment(target, url, slot);
        Object identity = fixture.onMain(() -> field(activity, "identity"));
        require(identity != null && Integer.valueOf(slot).equals(field(identity, "slot")),
                "Chromium opened a different environment than the fixture owner");
        return activity;
    }

    private void close(Activity activity) throws Exception {
        fixture.onMain(() -> { activity.finish(); return null; });
        fixture.waitForIdleSync();
    }

    private void files(Bundle result) throws Exception {
        String title = "FixtureFiles-" + nonce;
        String uploadName = "pc-upload-" + nonce + ".txt";
        String uploadBody = "Owned attachment " + nonce + "\n";
        Document pdf = new Document("fixture-" + nonce + ".pdf", "application/pdf", pdf());
        Document docx = new Document("fixture-" + nonce + ".docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx());
        String page = "<!doctype html><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<title>" + title + "</title><h1 id='proof'>" + title + "</h1>"
                + "<input id='upload' type='file' accept='text/plain'><pre id='selected'></pre>"
                + "<p><a id='pdf' href='/" + pdf.name + "' download>Download PDF</a></p>"
                + "<p><a id='word' href='/" + docx.name + "' download>Download Word</a></p>"
                + "<style>input,a{display:block;padding:12px}</style>"
                + "<script>document.getElementById('upload').onchange=async function(){let f=this.files[0];"
                + "document.getElementById('selected').textContent=f?f.name+'\\n'+await f.text():'';}</script>";
        Uri source = publishUpload(uploadName, uploadBody);
        try (LoopbackProxy proxy = new LoopbackProxy(LoopbackProxy.Kind.HTTP, nonce, title, null,
                (request, cookies, output) -> {
                    if (request.equals("GET /files HTTP/1.1")) {
                        respond(output, HTML, "", page.getBytes(StandardCharsets.UTF_8));
                        return true;
                    }
                    for (Document file : new Document[]{pdf, docx}) {
                        if (request.equals("GET /" + file.name + " HTTP/1.1")) {
                            file.requests.incrementAndGet();
                            respond(output, file.mime, "Content-Disposition: attachment; filename=\"" + file.name + "\"\r\n", file.bytes);
                            return true;
                        }
                    }
                    return false;
                })) {
            Activity activity = open(proxy, "/files", 1, true);
            try {
                CefriumBrowser browser = fixture.awaitBrowser(activity);
                fixture.requireMockRender(browser, proxy, title);
                recordLiveRenderer(result);
                tap(browser, "upload");
                selectDocument(uploadName);
                String expectedUpload = JSONObject.quote(uploadName + "\n" + uploadBody);
                await("selected file returned to the non-default Chromium page", () -> expectedUpload.equals(
                        fixture.evaluate(browser, "document.getElementById('selected')?.textContent")));
                require((proxy.origin() + "/files").equals(fixture.onMain(browser::getUrl)),
                        "Selected bytes must return to the owning Chromium page");
                result.putBoolean("androidDocumentsPickerOpened", true);
                result.putBoolean("selectedUploadBytesMatched", true);
                result.putInt("fileOwnerSlot", 1);

                result.putString("pdfSha256", download(browser, activity, "pdf", pdf));
                result.putString("docxSha256", download(browser, activity, "word", docx));
                require(proxy.handshakes.get() > 0 && pdf.requests.get() == 1 && docx.requests.get() == 1,
                        "Documents must use the exact isolated HTTP proxy once each");
                proxy.validate();
                result.putBoolean("realPdfAndDocxSavedBytesMatched", true);
            } finally {
                close(activity);
            }
        } finally {
            target.getContentResolver().delete(source, null, null);
        }
    }

    private String download(CefriumBrowser browser, Activity activity, String element, Document file) throws Exception {
        tap(browser, element);
        Object store = fixture.onMain(() -> field(field(activity, "files"), "store"));
        JSONObject[] seen = {null};
        await("published " + file.name, () -> {
            JSONArray rows = (JSONArray)invoke(store.getClass(), store, "rows", new Class<?>[0]);
            for (int index = 0; index < rows.length(); index++) {
                JSONObject row = rows.getJSONObject(index);
                if (!file.name.equals(row.optString("name"))) continue;
                require(seen[0] == null, "Duplicate saved document");
                seen[0] = row;
            }
            return seen[0] != null;
        });
        JSONObject row = seen[0];
        require(row.optInt("slot", -1) == 1 && file.mime.equals(row.optString("mime")),
                "The saved document name, type or owner did not match the fixture");
        Uri uri = Uri.parse(row.getString("uri"));
        require("content".equals(uri.getScheme()), "Saved document lacks a published Android URI");
        try (InputStream input = target.getContentResolver().openInputStream(uri)) {
            require(input != null, "Published document bytes cannot be read");
            ByteArrayOutputStream saved = new ByteArrayOutputStream();
            byte[] buffer = new byte[4096];
            for (int length; (length = input.read(buffer)) != -1; ) {
                require(saved.size() + length <= file.bytes.length, "Published document exceeded its expected length");
                saved.write(buffer, 0, length);
            }
            require(Arrays.equals(saved.toByteArray(), file.bytes), "Published document byte mismatch");
        }
        await("download publication completed", () -> fixture.onMain(() ->
                field(field(activity, "files"), "transfer") == null));
        return sha256(file.bytes);
    }

    private Uri publishUpload(String name, String body) throws Exception {
        ContentValues fields = new ContentValues();
        fields.put(MediaStore.MediaColumns.DISPLAY_NAME, name);
        fields.put(MediaStore.MediaColumns.MIME_TYPE, "text/plain");
        fields.put(MediaStore.MediaColumns.RELATIVE_PATH, "Download/");
        fields.put(MediaStore.MediaColumns.IS_PENDING, 1);
        Uri uri = target.getContentResolver().insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, fields);
        require(uri != null, "Could not create the isolated MediaStore upload input");
        boolean published = false;
        try {
            try (OutputStream output = target.getContentResolver().openOutputStream(uri)) {
                require(output != null, "The synthetic MediaStore file is not writable");
                output.write(body.getBytes(StandardCharsets.UTF_8));
            }
            ContentValues ready = new ContentValues();
            ready.put(MediaStore.MediaColumns.IS_PENDING, 0);
            require(target.getContentResolver().update(uri, ready, null, null) == 1, "Synthetic upload file was not published");
            published = true;
            return uri;
        } finally {
            if (!published) target.getContentResolver().delete(uri, null, null);
        }
    }

    private void tap(CefriumBrowser browser, String element) throws Exception {
        String position = fixture.evaluate(browser, "(()=>{const e=document.getElementById(" + JSONObject.quote(element)
                + ");if(!e)return null;const r=e.getBoundingClientRect();return [r.x+r.width/2,r.y+r.height/2];})()");
        require(position != null && position.startsWith("["), "Missing the Chromium fixture click target");
        JSONArray point = new JSONArray(position);
        fixture.onMain(() -> { browser.sendTap((float)point.getDouble(0), (float)point.getDouble(1)); return null; });
    }

    private void selectDocument(String name) throws Exception {
        UiAutomation automation = fixture.getUiAutomation();
        boolean drawerOpened = false, downloadsChosen = false;
        long deadline = SystemClock.elapsedRealtime() + 25_000;
        while (SystemClock.elapsedRealtime() < deadline) {
            AccessibilityNodeInfo root = automation.getRootInActiveWindow();
            CharSequence owner = root == null ? null : root.getPackageName();
            if (owner != null && ("com.android.documentsui".contentEquals(owner)
                    || "com.google.android.documentsui".contentEquals(owner))) {
                if (click(root, name)) return;
                if (drawerOpened && !downloadsChosen) downloadsChosen = click(root, "Downloads");
                if (!drawerOpened) drawerOpened = click(root, "Show roots") || click(root, "Open from");
            }
            SystemClock.sleep(200);
        }
        throw new IOException("Android DocumentsUI did not offer the owned synthetic input");
    }

    private static boolean click(AccessibilityNodeInfo root, String label) {
        ArrayDeque<AccessibilityNodeInfo> nodes = new ArrayDeque<>();
        nodes.add(root);
        for (int scanned = 0; !nodes.isEmpty() && scanned < 1024; scanned++) {
            AccessibilityNodeInfo node = nodes.removeFirst();
            if ((node.getText() != null && label.contentEquals(node.getText()))
                    || (node.getContentDescription() != null && label.contentEquals(node.getContentDescription()))) {
                for (AccessibilityNodeInfo owner = node; owner != null; owner = owner.getParent()) {
                    if (owner.isClickable()) return owner.performAction(AccessibilityNodeInfo.ACTION_CLICK);
                }
            }
            for (int i = 0; i < node.getChildCount(); i++) {
                AccessibilityNodeInfo child = node.getChild(i);
                if (child != null) nodes.addLast(child);
            }
        }
        return false;
    }

    private void profiles(boolean seed, Bundle result) throws Exception {
        String[] profileNames = new String[2];
        AtomicInteger[] witnessed = {new AtomicInteger(), new AtomicInteger()};
        AtomicInteger[] requests = {new AtomicInteger(), new AtomicInteger()};
        try (LoopbackProxy proxy = new LoopbackProxy(LoopbackProxy.Kind.HTTP, nonce, "FixtureProfiles", null,
                (request, cookies, output) -> {
                    for (int slot = 0; slot < 2; slot++) {
                        if (!request.equals("GET /state-" + slot + " HTTP/1.1")) continue;
                        requests[slot].incrementAndGet();
                        String value = nonce + "-env-" + slot;
                        boolean expectedCookie = Arrays.asList(cookies.split(";\\s*")).contains(COOKIE + "=" + value);
                        boolean anyCookie = Arrays.stream(cookies.split(";\\s*")).anyMatch(item -> item.startsWith(COOKIE + "="));
                        if ((!seed && expectedCookie) || (seed && !anyCookie)) witnessed[slot].incrementAndGet();
                        String headers = seed ? "Set-Cookie: " + COOKIE + "=" + value + "; Path=/; Max-Age=86400; HttpOnly; SameSite=Lax\r\n" : "";
                        String page = "<!doctype html><title>FixtureProfiles-" + slot + "</title>"
                                + (seed ? "<script>window.pcBefore=localStorage.getItem('" + STORE
                                + "');localStorage.setItem('" + STORE + "','" + value + "');</script>" : "");
                        respond(output, HTML, headers, page.getBytes(StandardCharsets.UTF_8));
                        return true;
                    }
                    return false;
                })) {
            for (int slot = 0; slot < 2; slot++) {
                Activity activity = open(proxy, "/state-" + slot, slot, seed);
                try {
                    CefriumBrowser browser = fixture.awaitBrowser(activity);
                    fixture.awaitRenderedTitle(browser, "FixtureProfiles-" + slot);
                    recordLiveRenderer(result);
                    String expected = JSONObject.quote(nonce + "-env-" + slot);
                    await("expected owned Chromium site-storage value", () -> expected.equals(
                            fixture.evaluate(browser, "localStorage.getItem(" + JSONObject.quote(STORE) + ")")));
                    if (seed) require("true".equals(fixture.evaluate(browser, "window.pcBefore===null")),
                            "A different Chromium environment already had the seeded local-storage value");
                    require(requests[slot].get() == 1 && witnessed[slot].get() == 1,
                            "The browser did not send the exact expected isolated HttpOnly cookie state");
                    CefriumProfile profile = fixture.onMain(browser::getProfile);
                    require(!profile.isIncognito() && profile.getDirectory() != null,
                            "Chromium did not use a persistent native profile");
                    profileNames[slot] = profile.getName();
                    if (seed) {
                        CountDownLatch flushed = new CountDownLatch(1);
                        fixture.onMain(() -> { profile.getCookieManager().flush(flushed::countDown); return null; });
                        require(flushed.await(10, TimeUnit.SECONDS), "Chromium cookie flush did not finish");
                    }
                } finally {
                    close(activity);
                }
            }
            proxy.validate();
        }
        // The SDK can flush cookies directly. DOM storage commits its writes asynchronously.
        if (seed) SystemClock.sleep(6_000);
        require(!profileNames[0].equals(profileNames[1]), "Both environments shared the same native Chromium profile");
        result.putString("profile0Sha256", sha256(profileNames[0].getBytes(StandardCharsets.UTF_8)));
        result.putString("profile1Sha256", sha256(profileNames[1].getBytes(StandardCharsets.UTF_8)));
        result.putBoolean("twoChromiumProfilesIsolated", true);
        result.putBoolean("persistentHttpOnlyCookieRead", !seed);
        result.putBoolean("persistentLocalStorageRead", !seed);
    }

    private void recordLiveRenderer(Bundle result) throws Exception {
        int renderers = fixture.onMain(CefriumBrowser::activeRenderProcessCount);
        require(renderers > 0, "The native Chromium renderer is not active");
        result.putInt("nativeRenderers", renderers);
    }

    private interface Condition { boolean ready() throws Exception; }

    private static void await(String description, Condition condition) throws Exception {
        long deadline = SystemClock.elapsedRealtime() + 30_000;
        while (SystemClock.elapsedRealtime() < deadline) {
            if (condition.ready()) return;
            SystemClock.sleep(250);
        }
        throw new IOException("Timed out waiting for " + description);
    }

    private static void respond(OutputStream output, String type, String headers, byte[] bytes) throws IOException {
        output.write(("HTTP/1.1 200 OK\r\nConnection: close\r\nCache-Control: no-store\r\nContent-Type: " + type
                + "\r\n" + headers + "Content-Length: " + bytes.length + "\r\n\r\n").getBytes(StandardCharsets.US_ASCII));
        output.write(bytes);
        output.flush();
    }

    private static byte[] pdf() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        PdfDocument document = new PdfDocument();
        try {
            PdfDocument.Page page = document.startPage(new PdfDocument.PageInfo.Builder(360, 480, 1).create());
            Paint text = new Paint();
            text.setTextSize(16);
            page.getCanvas().drawText("PocketChat PDF fixture", 20, 40, text);
            document.finishPage(page);
            document.writeTo(bytes);
        } finally {
            document.close();
        }
        return bytes.toByteArray();
    }

    private static byte[] docx() throws IOException {
        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
        try (ZipOutputStream zip = new ZipOutputStream(bytes)) {
            xml(zip, "[Content_Types].xml", "<Types xmlns='http://schemas.openxmlformats.org/package/2006/content-types'>"
                    + "<Default Extension='rels' ContentType='application/vnd.openxmlformats-package.relationships+xml'/>"
                    + "<Default Extension='xml' ContentType='application/xml'/>"
                    + "<Override PartName='/word/document.xml' ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml'/></Types>");
            xml(zip, "_rels/.rels", "<Relationships xmlns='http://schemas.openxmlformats.org/package/2006/relationships'>"
                    + "<Relationship Id='rId1' Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument' Target='word/document.xml'/></Relationships>");
            xml(zip, "word/document.xml", "<w:document xmlns:w='http://schemas.openxmlformats.org/wordprocessingml/2006/main'>"
                    + "<w:body><w:p><w:r><w:t>PocketChat Word fixture</w:t></w:r></w:p></w:body></w:document>");
        }
        return bytes.toByteArray();
    }

    private static void xml(ZipOutputStream zip, String name, String body) throws IOException {
        ZipEntry entry = new ZipEntry(name);
        entry.setTime(0);
        zip.putNextEntry(entry);
        zip.write(body.getBytes(StandardCharsets.UTF_8));
        zip.closeEntry();
    }

    private static String sha256(byte[] value) throws Exception {
        StringBuilder hex = new StringBuilder();
        for (byte octet : MessageDigest.getInstance("SHA-256").digest(value)) {
            hex.append(String.format(Locale.ROOT, "%02x", octet & 0xff));
        }
        return hex.toString();
    }

    private static final class Document {
        final String name, mime;
        final byte[] bytes;
        final AtomicInteger requests = new AtomicInteger();

        Document(String name, String mime, byte[] bytes) {
            this.name = name;
            this.mime = mime;
            this.bytes = bytes;
        }
    }
}
