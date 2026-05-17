@echo off
REM Zihin Koprusu Windows .bat Istemci
REM Uzuv: Windows BAT Ajan (windows_bat_ajan)
REM Merkez: avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion:22
REM Gereksinim: OpenSSH (Win10+), Tor Expert Bundle

set SUNUCU=avlihkczlpvz7cd423a3ydmoemkyeviw6xcya4zcxlqa43biaiaftqyd.onion
set PORT=22
set KULLANICI=zihin
set TOR_PROXY=127.0.0.1:9050
set YEREL_PORT=2222

echo [ZK] Baslaniyor...

:DONGU
echo [ZK] Baglaniliyor...
ssh -N -R %YEREL_PORT%:localhost:22 ^
    -o StrictHostKeyChecking=no ^
    -o ServerAliveInterval=30 ^
    -p %PORT% ^
    -o "ProxyCommand=nc -x %TOR_PROXY% %%h %%p" ^
    %KULLANICI%@%SUNUCU%

echo [ZK] Kesildi. 15 saniye bekleniyor...
timeout /t 15 /nobreak >nul
goto DONGU
