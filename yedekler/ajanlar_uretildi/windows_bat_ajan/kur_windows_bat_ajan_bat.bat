@echo off
setlocal
cd /d "%~dp0"
echo [ZK] Windows BAT ajan kurulumu - Windows BAT Ajan
where ssh >nul 2>&1 || (echo [HATA] OpenSSH bulunamadi. Windows Ozellikleri > OpenSSH Client etkinlestirin.& pause & exit /b 1)
echo [ZK] Zamanlanmis gorev kuruluyor: ZK-BAT-windows_bat_ajan
schtasks /Create /TN "ZK-BAT-windows_bat_ajan" /TR "cmd /c \"%~dp0zk_windows_bat_ajan.bat\"" /SC ONLOGON /RL HIGHEST /F
if %errorlevel% neq 0 (
    echo [HATA] Gorev kurulamadi. Bu dosyayi Yonetici olarak calistirin.
    pause
    exit /b 1
)
echo [ZK] Gorev baslatiliyor...
schtasks /Run /TN "ZK-BAT-windows_bat_ajan"
echo [ZK] Kurulum tamamlandi.
pause
