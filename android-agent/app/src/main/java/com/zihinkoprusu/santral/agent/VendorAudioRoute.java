package com.zihinkoprusu.santral.agent;

import android.media.AudioManager;
import android.net.LocalSocket;
import android.net.LocalSocketAddress;
import android.util.Log;

import java.io.OutputStream;
import java.nio.charset.StandardCharsets;

public final class VendorAudioRoute {
    private static final String TAG = "ZKSantralAgent";

    private VendorAudioRoute() {}

    public static void prepare(AudioManager audioManager) {
        if (audioManager == null) {
            return;
        }

        try {
            audioManager.setMode(AudioManager.MODE_IN_CALL);
            Log.i(TAG, "vendor route: mode=IN_CALL");
        } catch (Throwable exc) {
            Log.w(TAG, "vendor route: MODE_IN_CALL failed", exc);
        }

        try {
            audioManager.setSpeakerphoneOn(true);
            Log.i(TAG, "vendor route: speaker on");
        } catch (Throwable exc) {
            Log.w(TAG, "vendor route: speaker enable failed", exc);
        }

        for (String param : AgentConfig.VENDOR_AUDIO_PARAMS) {
            try {
                audioManager.setParameters(param);
                Log.i(TAG, "vendor route: setParameters " + param);
            } catch (Throwable exc) {
                Log.w(TAG, "vendor route: setParameters failed " + param, exc);
            }
        }

        if (!AgentConfig.ENABLE_ATCI_ROUTE) {
            return;
        }

        for (String command : AgentConfig.ATCI_ROUTE_COMMANDS) {
            try {
                sendAtci(command);
                Log.i(TAG, "vendor route: atci sent " + command);
            } catch (Throwable exc) {
                Log.w(TAG, "vendor route: atci failed " + command, exc);
            }
        }
    }

    public static void restore(AudioManager audioManager) {
        if (audioManager == null) {
            return;
        }
        try {
            audioManager.setMode(AudioManager.MODE_NORMAL);
            Log.i(TAG, "vendor route: mode=NORMAL");
        } catch (Throwable exc) {
            Log.w(TAG, "vendor route: restore mode failed", exc);
        }
    }

    private static void sendAtci(String command) throws Exception {
        sendSocket("atci-audio", LocalSocketAddress.Namespace.RESERVED, command);
    }

    private static void sendSocket(
        String target,
        LocalSocketAddress.Namespace namespace,
        String command
    ) throws Exception {
        try (LocalSocket socket = new LocalSocket()) {
            socket.connect(new LocalSocketAddress(target, namespace));
            try (OutputStream out = socket.getOutputStream()) {
                out.write((command + "\r\n").getBytes(StandardCharsets.UTF_8));
                out.flush();
            }
        }
    }
}
