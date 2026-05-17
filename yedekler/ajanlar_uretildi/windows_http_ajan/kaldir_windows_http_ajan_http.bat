@echo off
echo [ZK] Zamanlanmis gorev kaldiriliyor: ZK-HTTP-windows_http_ajan
schtasks /End /TN "ZK-HTTP-windows_http_ajan" >nul 2>&1
schtasks /Delete /TN "ZK-HTTP-windows_http_ajan" /F
echo [ZK] Kaldirma tamamlandi.
pause
