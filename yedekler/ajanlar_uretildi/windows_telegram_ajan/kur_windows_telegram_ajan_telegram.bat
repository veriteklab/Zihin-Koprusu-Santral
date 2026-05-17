@echo off
setlocal
cd /d "%~dp0"
echo [ZK] Telegram ajan kurulumu - Windows Telegram Ajan
python --version >nul 2>&1 || (echo [HATA] Python bulunamadi.& pause & exit /b 1)
python -m pip install --upgrade telethon
echo [ZK] Zamanlanmis gorev kuruluyor: ZK-Telegram-windows_telegram_ajan
schtasks /Create /TN "ZK-Telegram-windows_telegram_ajan" /TR "python \"%~dp0zk_windows_telegram_ajan_telegram.py\"" /SC ONLOGON /RL HIGHEST /F
if %errorlevel% neq 0 (
    echo [HATA] Gorev kurulamadi. Bu dosyayi Yonetici olarak calistirin.
    pause
    exit /b 1
)
echo [ZK] Gorev baslatiliyor...
schtasks /Run /TN "ZK-Telegram-windows_telegram_ajan"
echo [ZK] Kurulum tamamlandi.
pause
