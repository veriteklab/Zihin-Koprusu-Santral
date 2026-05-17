@echo off
echo [ZK] Zamanlanmis gorev kaldiriliyor: ZK-Telegram-windows_telegram_ajan
schtasks /End /TN "ZK-Telegram-windows_telegram_ajan" >nul 2>&1
schtasks /Delete /TN "ZK-Telegram-windows_telegram_ajan" /F
echo [ZK] Kaldirma tamamlandi.
pause
