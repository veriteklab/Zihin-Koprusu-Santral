package com.zihinkoprusu.santral.agent;

public final class AgentConfig {
    private AgentConfig() {}

    public static final String SERVER_URL = "__SERVER_URL__";
    public static final String TOKEN = "__TOKEN__";
    public static final String DEVICE_ID = "__DEVICE_ID__";
    public static final boolean AUTO_ANSWER = false;
    public static final boolean AUTO_PLAY_PROMPT = true;
    public static final boolean ENABLE_ATCI_ROUTE = true;
    public static final String[] VENDOR_AUDIO_PARAMS = new String[] {
        "incall_music_enabled=true",
        "incall_music_enabled=1",
        "incall_music=true",
        "SetIncallMusic=1",
        "MTK_VOIP_ENHANCEMENT=1",
        "Routing=2"
    };
    public static final String[] ATCI_ROUTE_COMMANDS = new String[] {
        "AUD+MODESEL=1",
        "AUD+RECEIVER=1",
        "AUD+AMPEN=1"
    };
}
