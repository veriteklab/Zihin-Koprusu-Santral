package com.zihinkoprusu.santral.agent;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Build;
import android.view.KeyEvent;
import android.view.View;
import android.view.WindowManager;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.JavascriptInterface;
import android.net.Uri;

public class MainActivity extends Activity {
    private WebView webView;
    private final View.OnSystemUiVisibilityChangeListener kioskUiListener =
        visibility -> {
            int fullscreenFlags = View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION;
            if ((visibility & fullscreenFlags) != fullscreenFlags) {
                enterImmersiveMode();
            }
        };

    public static class DashboardBridge {
        @JavascriptInterface
        public String getServerUrl() {
            return AgentConfig.SERVER_URL;
        }

        @JavascriptInterface
        public String getDeviceId() {
            return AgentConfig.DEVICE_ID;
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.BLACK);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setAllowFileAccess(true);
        settings.setAllowContentAccess(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.JELLY_BEAN) {
            settings.setAllowFileAccessFromFileURLs(true);
            settings.setAllowUniversalAccessFromFileURLs(true);
        }

        webView.setWebChromeClient(new WebChromeClient());
        webView.setLongClickable(false);
        webView.setHapticFeedbackEnabled(false);
        webView.setHorizontalScrollBarEnabled(false);
        webView.setVerticalScrollBarEnabled(false);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return shouldBlockNavigation(url);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, android.webkit.WebResourceRequest request) {
                return shouldBlockNavigation(request.getUrl().toString());
            }
        });
        webView.addJavascriptInterface(new DashboardBridge(), "SantralBridge");
        setContentView(webView);
        getWindow().getDecorView().setOnSystemUiVisibilityChangeListener(kioskUiListener);

        webView.loadUrl("file:///android_asset/dashboard/index.html");
        enterImmersiveMode();
        tryStartLockTask();
    }

    @Override
    protected void onResume() {
        super.onResume();
        enterImmersiveMode();
        tryStartLockTask();
        if (webView != null) {
            webView.onResume();
            webView.resumeTimers();
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
            webView.pauseTimers();
        }
        super.onPause();
    }

    @Override
    public void onBackPressed() {
        // Intentional no-op for kiosk behavior.
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK
            || keyCode == KeyEvent.KEYCODE_MENU
            || keyCode == KeyEvent.KEYCODE_SEARCH
            || keyCode == KeyEvent.KEYCODE_APP_SWITCH) {
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (hasFocus) {
            enterImmersiveMode();
        }
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        if (webView != null) {
            webView.reload();
        }
    }

    private void tryStartLockTask() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            try {
                startLockTask();
            } catch (Exception ignored) {
            }
        }
    }

    private void enterImmersiveMode() {
        View decorView = getWindow().getDecorView();
        decorView.setSystemUiVisibility(
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                | View.SYSTEM_UI_FLAG_FULLSCREEN
                | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
        );
    }

    private boolean shouldBlockNavigation(String url) {
        if (url == null || url.isEmpty()) {
            return false;
        }
        if (url.startsWith("file:///android_asset/dashboard/")) {
            return false;
        }
        String serverUrl = AgentConfig.SERVER_URL;
        if (serverUrl != null && !serverUrl.contains("__SERVER_URL__")) {
            Uri allowed = Uri.parse(serverUrl);
            Uri target = Uri.parse(url);
            if (allowed.getScheme() != null
                && allowed.getHost() != null
                && allowed.getScheme().equalsIgnoreCase(target.getScheme())
                && allowed.getHost().equalsIgnoreCase(target.getHost())) {
                return false;
            }
        }
        return true;
    }
}
