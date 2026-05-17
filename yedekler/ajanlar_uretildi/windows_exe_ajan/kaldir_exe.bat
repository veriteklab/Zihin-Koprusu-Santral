@echo off
echo [ZK] Zamanlanmis gorev kaldiriliyor: ZK-EXE-windows_exe_ajan
schtasks /End /TN "ZK-EXE-windows_exe_ajan" >nul 2>&1
schtasks /Delete /TN "ZK-EXE-windows_exe_ajan" /F
echo [ZK] Kaldirma tamamlandi.
pause
