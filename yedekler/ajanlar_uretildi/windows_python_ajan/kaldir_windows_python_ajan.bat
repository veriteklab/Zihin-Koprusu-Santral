@echo off
echo [ZK] Zamanlanmis gorev kaldiriliyor: ZK-SSH-windows_python_ajan
schtasks /End /TN "ZK-SSH-windows_python_ajan" >nul 2>&1
schtasks /Delete /TN "ZK-SSH-windows_python_ajan" /F
echo [ZK] Kaldirma tamamlandi.
pause
