@echo off
echo [ZK] Zamanlanmis gorev kaldiriliyor: ZK-BAT-windows_bat_ajan
schtasks /End /TN "ZK-BAT-windows_bat_ajan" >nul 2>&1
schtasks /Delete /TN "ZK-BAT-windows_bat_ajan" /F
echo [ZK] Kaldirma tamamlandi.
pause
