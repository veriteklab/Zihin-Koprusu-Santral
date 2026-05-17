package com.zihinkoprusu.santral.agent;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.telephony.TelephonyManager;

public class PhoneStateReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (!TelephonyManager.ACTION_PHONE_STATE_CHANGED.equals(intent.getAction())) {
            return;
        }

        String state = intent.getStringExtra(TelephonyManager.EXTRA_STATE);
        String incomingNumber = intent.getStringExtra(TelephonyManager.EXTRA_INCOMING_NUMBER);

        Intent serviceIntent = new Intent(context, CallAgentService.class);
        serviceIntent.putExtra("phone_state", state == null ? "" : state);
        serviceIntent.putExtra("incoming_number", incomingNumber == null ? "" : incomingNumber);
        context.startService(serviceIntent);
    }
}
