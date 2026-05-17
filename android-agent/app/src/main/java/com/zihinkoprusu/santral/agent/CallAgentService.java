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

public class CallAgentService extends Service {
    private static final String TAG = "ZKSantralAgent";

    private String currentCallId = "";
    private String previousState = TelephonyManager.EXTRA_STATE_IDLE;

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

        try {
            if (TelephonyManager.EXTRA_STATE_RINGING.equals(state)
                && !TelephonyManager.EXTRA_STATE_RINGING.equals(previousState)) {
                currentCallId = String.valueOf(System.currentTimeMillis() / 1000L);
                SantralApi.postEvent(currentCallId, "incoming", incomingNumber, "ringing");
                if (AgentConfig.AUTO_ANSWER) {
                    RootActions.autoAnswer();
                }
            } else if (TelephonyManager.EXTRA_STATE_OFFHOOK.equals(state)
                && !TelephonyManager.EXTRA_STATE_OFFHOOK.equals(previousState)) {
                if (currentCallId.isEmpty()) {
                    currentCallId = String.valueOf(System.currentTimeMillis() / 1000L);
                }
                SantralApi.postEvent(currentCallId, "answered", incomingNumber, "active");
                if (AgentConfig.AUTO_PLAY_PROMPT) {
                    playPrompt(currentCallId);
                }
            } else if (TelephonyManager.EXTRA_STATE_IDLE.equals(state)
                && !TelephonyManager.EXTRA_STATE_IDLE.equals(previousState)) {
                if (!currentCallId.isEmpty()) {
                    SantralApi.postEvent(currentCallId, "hangup", incomingNumber, "idle");
                }
                currentCallId = "";
            }
        } catch (Exception exc) {
            Log.e(TAG, "call flow failed", exc);
        }

        previousState = state;
        return START_NOT_STICKY;
    }

    private void playPrompt(String callId) {
        try {
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
                audioManager.setMode(AudioManager.MODE_IN_CALL);
            }

            MediaPlayer player = new MediaPlayer();
            player.setAudioStreamType(AudioManager.STREAM_VOICE_CALL);
            player.setDataSource(target.getAbsolutePath());
            player.setOnCompletionListener(mp -> {
                mp.release();
                stopSelf();
            });
            player.prepare();
            player.start();
        } catch (Exception exc) {
            Log.e(TAG, "prompt playback failed", exc);
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
