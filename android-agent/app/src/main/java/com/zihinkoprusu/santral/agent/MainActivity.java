package com.zihinkoprusu.santral.agent;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        TextView text = new TextView(this);
        text.setPadding(32, 32, 32, 32);
        text.setText(
            "ZK Santral Agent\n\n" +
            "Bu ajan gelen cagrilari izler, backend'e olay yollar, " +
            "otomatik cevap ve prompt oynatma akisini yurutur."
        );
        setContentView(text);
    }
}
