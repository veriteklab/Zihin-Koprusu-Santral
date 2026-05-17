package com.zihinkoprusu.santral.agent;

import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

public final class SantralApi {
    private SantralApi() {}

    public static void postEvent(String callId, String eventType, String phoneNumber, String state) throws Exception {
        URL url = new URL(AgentConfig.SERVER_URL + "/api/v1/events");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(10000);
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");

        JSONObject payload = new JSONObject();
        payload.put("token", AgentConfig.TOKEN);
        payload.put("device_id", AgentConfig.DEVICE_ID);
        payload.put("event_type", eventType);
        payload.put("phone_number", phoneNumber);
        payload.put("state", state);
        payload.put("call_id", callId);

        try (OutputStream out = conn.getOutputStream()) {
            out.write(payload.toString().getBytes(StandardCharsets.UTF_8));
        }

        int code = conn.getResponseCode();
        if (code < 200 || code >= 300) {
            throw new IllegalStateException("postEvent failed: " + code);
        }
        conn.disconnect();
    }

    public static String fetchLatestActiveCallId() throws Exception {
        URL url = new URL(
            AgentConfig.SERVER_URL
                + "/api/v1/devices/" + AgentConfig.DEVICE_ID
                + "/latest-call?token=" + AgentConfig.TOKEN
                + "&state=active"
        );
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(10000);
        conn.setReadTimeout(10000);

        int code = conn.getResponseCode();
        if (code != 200) {
            conn.disconnect();
            return null;
        }

        try (InputStream in = conn.getInputStream();
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            JSONObject json = new JSONObject(out.toString(StandardCharsets.UTF_8.name()));
            if (!json.optBoolean("ok", false)) {
                return null;
            }
            return json.optString("call_id", null);
        } finally {
            conn.disconnect();
        }
    }

    public static byte[] fetchPromptAudio(String callId) throws Exception {
        URL url = new URL(
            AgentConfig.SERVER_URL
                + "/api/v1/calls/" + callId
                + "/prompt-audio?token=" + AgentConfig.TOKEN
        );
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("GET");
        conn.setConnectTimeout(15000);
        conn.setReadTimeout(30000);

        int code = conn.getResponseCode();
        if (code != 200) {
            conn.disconnect();
            return null;
        }

        try (InputStream in = conn.getInputStream();
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
            return out.toByteArray();
        } finally {
            conn.disconnect();
        }
    }
}
