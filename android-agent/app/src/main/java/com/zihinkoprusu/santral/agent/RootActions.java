package com.zihinkoprusu.santral.agent;

public final class RootActions {
    private RootActions() {}

    public static void autoAnswer() {
        execRoot("input keyevent KEYCODE_HEADSETHOOK");
    }

    private static void execRoot(String command) {
        Process process = null;
        try {
            process = Runtime.getRuntime().exec(new String[] {
                "su", "-c", command
            });
            process.waitFor();
        } catch (Exception ignored) {
        } finally {
            if (process != null) {
                process.destroy();
            }
        }
    }
}
