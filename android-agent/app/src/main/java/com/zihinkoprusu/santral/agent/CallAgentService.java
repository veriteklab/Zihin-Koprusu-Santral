package com.zihinkoprusu.santral.agent;

import android.app.Service;
import android.content.Intent;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.os.IBinder;
import android.telephony.TelephonyManager;
import android.util.Log;

import java.io.File;
import java.io.FileOutputStream;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class CallAgentService extends Service {
    private static final String TAG = "ZKSantralAgent";
    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();

    private String previousState = TelephonyManager.EXTRA_STATE_IDLE;
    private String lastPlayedCallId = "";

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) {
            return START_NOT_STICKY;
        }

        String state = intent.getStringExtra("phone_state");
        String incomingNumber = intent.getStringExtra("incoming_number");
        if (state == null) {
            state = "";
        }
        if (incomingNumber == null) {
            incomingNumber = "";
        }

        final String finalState = state;
        final String finalIncomingNumber = incomingNumber;
        EXECUTOR.execute(() -> handleCallState(finalState, finalIncomingNumber));

        previousState = state;
        return START_NOT_STICKY;
    }

    private void handleCallState(String state, String incomingNumber) {
        try {
            if (TelephonyManager.EXTRA_STATE_RINGING.equals(state)
                && !TelephonyManager.EXTRA_STATE_RINGING.equals(previousState)) {
                if (AgentConfig.AUTO_ANSWER) {
                    RootActions.autoAnswer();
                }
            } else if (TelephonyManager.EXTRA_STATE_OFFHOOK.equals(state)
                && !TelephonyManager.EXTRA_STATE_OFFHOOK.equals(previousState)) {
                if (AgentConfig.AUTO_PLAY_PROMPT) {
                    playLatestPrompt();
                }
            } else if (TelephonyManager.EXTRA_STATE_IDLE.equals(state)
                && !TelephonyManager.EXTRA_STATE_IDLE.equals(previousState)) {
                lastPlayedCallId = "";
            }
        } catch (Exception exc) {
            Log.e(TAG, "call flow failed", exc);
        }
    }

    private void playLatestPrompt() {
        try {
            String callId = null;
            for (int i = 0; i < 6; i++) {
                callId = SantralApi.fetchLatestActiveCallId();
                if (callId != null && !callId.isEmpty()) {
                    break;
                }
                Thread.sleep(500);
            }
            if (callId == null || callId.isEmpty()) {
                Log.w(TAG, "latest active call not found");
                return;
            }
            if (callId.equals(lastPlayedCallId)) {
                Log.i(TAG, "prompt already played for " + callId);
                return;
            }
            byte[] audio = SantralApi.fetchPromptAudio(callId);
            if (audio == null || audio.length == 0) {
                return;
            }
            File target = new File(getCacheDir(), callId + "_prompt.mp3");
            try (FileOutputStream out = new FileOutputStream(target)) {
                out.write(audio);
            }

            AudioManager audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audioManager != null) {
                audioManager.setSpeakerphoneOn(true);
                audioManager.setMode(AudioManager.MODE_NORMAL);
            }

            MediaPlayer player = new MediaPlayer();
            player.setAudioStreamType(AudioManager.STREAM_MUSIC);
            player.setDataSource(target.getAbsolutePath());
            player.setOnCompletionListener(mp -> {
                mp.release();
                stopSelf();
            });
            player.prepare();
            player.start();
            lastPlayedCallId = callId;
        } catch (Exception exc) {
            Log.e(TAG, "prompt playback failed", exc);
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
