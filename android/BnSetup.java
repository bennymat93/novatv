package org.bn.stream;

import android.content.Context;
import android.util.Log;

import java.io.BufferedInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipInputStream;

/**
 * First start of BN Stream: unpack the BN build (assets/bn_build.zip) into Kodi's home
 * before Kodi itself starts, so the app opens fully configured - no wizard, no restart.
 * Called from Splash$FillCache.doInBackground (background thread).
 * A newer build inside an updated APK is applied the same way (addons + defaults),
 * while personal data in userdata/addon_data is kept.
 */
public final class BnSetup {
    private static final String TAG = "BnSetup";
    private static final String MARK = "userdata/novatv_build.txt";

    public static void prepare(Context ctx) {
        try {
            String data = System.getProperty("xbmc.data", "");
            File base = data.isEmpty() ? ctx.getExternalFilesDir(null) : new File(data);
            File home = new File(base, ".kodi");
            String bundled = readAsset(ctx, "bn_build.txt");
            File mark = new File(home, MARK);
            String installed = mark.exists() ? readFile(mark) : "";
            if (!bundled.isEmpty() && bundled.equals(installed)) {
                return;
            }
            boolean update = mark.exists();
            Log.i(TAG, (update ? "updating" : "installing") + " BN build into " + home);
            String root = home.getCanonicalPath() + File.separator;
            byte[] buf = new byte[256 * 1024];
            try (ZipInputStream z = new ZipInputStream(new BufferedInputStream(ctx.getAssets().open("bn_build.zip"), 1 << 20))) {
                ZipEntry e;
                while ((e = z.getNextEntry()) != null) {
                    String name = e.getName();
                    if (name.equals(MARK)) {
                        continue;                        // written last = install complete
                    }
                    // on update keep the user's accounts, history, favourites and settings
                    if (update && name.startsWith("userdata/") && !name.startsWith("userdata/keymaps/")) {
                        continue;
                    }
                    File out = new File(home, name);
                    if (!out.getCanonicalPath().startsWith(root)) {
                        continue;                        // zip-slip guard
                    }
                    if (e.isDirectory()) {
                        out.mkdirs();
                        continue;
                    }
                    out.getParentFile().mkdirs();
                    try (OutputStream o = new FileOutputStream(out)) {
                        int n;
                        while ((n = z.read(buf)) > 0) {
                            o.write(buf, 0, n);
                        }
                    }
                }
            }
            mark.getParentFile().mkdirs();
            try (OutputStream o = new FileOutputStream(mark)) {
                o.write(bundled.getBytes("UTF-8"));
            }
            Log.i(TAG, "BN build ready: " + bundled.trim());
        } catch (Exception ex) {
            Log.e(TAG, "BN build setup failed", ex);
        }
    }

    private static String readAsset(Context ctx, String name) {
        try (InputStream in = ctx.getAssets().open(name)) {
            return readAll(in);
        } catch (Exception e) {
            return "";
        }
    }

    private static String readFile(File f) {
        try (InputStream in = new java.io.FileInputStream(f)) {
            return readAll(in);
        } catch (Exception e) {
            return "";
        }
    }

    private static String readAll(InputStream in) throws java.io.IOException {
        java.io.ByteArrayOutputStream b = new java.io.ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int n;
        while ((n = in.read(buf)) > 0) {
            b.write(buf, 0, n);
        }
        return b.toString("UTF-8");
    }
}
