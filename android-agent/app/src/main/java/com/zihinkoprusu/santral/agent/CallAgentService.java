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

        final String previousStateSnapshot = previousState;
        previousState = state;
        final String finalState = state;
        final String finalIncomingNumber = incomingNumber;
        EXECUTOR.execute(() -> handleCallState(finalState, finalIncomingNumber, previousStateSnapshot));
        return START_NOT_STICKY;
    }

    private void handleCallState(String state, String incomingNumber, String previousStateSnapshot) {
        try {
            Log.i(TAG, "state transition: " + previousStateSnapshot + " -> " + state + " number=" + incomingNumber);
            if (TelephonyManager.EXTRA_STATE_RINGING.equals(state)
                && !TelephonyManager.EXTRA_STATE_RINGING.equals(previousStateSnapshot)) {
                if (AgentConfig.AUTO_ANSWER) {
                    RootActions.autoAnswer();
                }
            } else if (TelephonyManager.EXTRA_STATE_OFFHOOK.equals(state)
                && !TelephonyManager.EXTRA_STATE_OFFHOOK.equals(previousStateSnapshot)) {
                if (AgentConfig.AUTO_PLAY_PROMPT) {
                    playLatestPrompt();
                }
            } else if (TelephonyManager.EXTRA_STATE_IDLE.equals(state)
                && !TelephonyManager.EXTRA_STATE_IDLE.equals(previousStateSnapshot)) {
                lastPlayedCallId = "";
                Log.i(TAG, "call returned to idle");
            }
        } catch (Exception exc) {
            Log.e(TAG, "call flow failed", exc);
        }
    }

    private void playLatestPrompt() {
        try {
            String callId = null;
            for (int i = 0; i < 60; i++) {
                callId = SantralApi.fetchLatestActiveCallId();
                if (callId != null && !callId.isEmpty()) {
                    break;
                }
                if (i == 0 || (i + 1) % 10 == 0) {
                    Log.i(TAG, "latest call waiting attempt=" + (i + 1));
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
            Log.i(TAG, "playing prompt for call " + callId);
            byte[] audio = SantralApi.fetchPromptAudio(callId);
            if (audio == null || audio.length == 0) {
                Log.w(TAG, "prompt audio empty for " + callId);
                return;
            }
            File target = new File(getCacheDir(), callId + "_prompt.mp3");
            try (FileOutputStream out = new FileOutputStream(target)) {
                out.write(audio);
            }
            Log.i(TAG, "prompt cached at " + target.getAbsolutePath() + " bytes=" + audio.length);

            AudioManager audioManager = (AudioManager) getSystemService(AUDIO_SERVICE);
            if (audioManager != null) {
                audioManager.setSpeakerphoneOn(true);
                forceMaxVolume(audioManager, AudioManager.STREAM_MUSIC);
                try {
                    audioManager.setMode(AudioManager.MODE_NORMAL);
                } catch (Exception exc) {
                    Log.w(TAG, "audio mode set failed", exc);
                }
            }

            Thread.sleep(1500);
            playWithStream(target, AudioManager.STREAM_MUSIC, "music_speaker");
            lastPlayedCallId = callId;
        } catch (Exception exc) {
            Log.e(TAG, "prompt playback failed", exc);
        }
    }

    private boolean playWithStream(File target, int streamType, String label) {
        MediaPlayer player = null;
        try {
            player = new MediaPlayer();
            player.setAudioStreamType(streamType);
            player.setDataSource(target.getAbsolutePath());
            final MediaPlayer finalPlayer = player;
            player.setOnCompletionListener(mp -> {
                Log.i(TAG, "prompt completed via " + label);
                mp.release();
                if (finalPlayer == mp) {
                    stopSelf();
                }
            });
            player.prepare();
            player.start();
            Log.i(TAG, "prompt started via " + label + " stream=" + streamType);
            return true;
        } catch (Exception exc) {
            Log.w(TAG, "prompt start failed via " + label, exc);
            if (player != null) {
                try {
                    player.release();
                } catch (Exception ignored) {
                }
            }
            return false;
        }
    }

    private void forceMaxVolume(AudioManager audioManager, int streamType) {
        try {
            int max = audioManager.getStreamMaxVolume(streamType);
            if (max > 0) {
                audioManager.setStreamVolume(streamType, max, 0);
                Log.i(TAG, "volume maxed stream=" + streamType + " max=" + max);
            }
        } catch (Exception exc) {
            Log.w(TAG, "volume set failed stream=" + streamType, exc);
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
