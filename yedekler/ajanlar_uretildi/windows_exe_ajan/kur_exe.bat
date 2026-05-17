@echo off
setlocal
cd /d "%~dp0"
echo [ZK] Windows EXE ajan kurulumu - Windows EXE Ajan
where ssh >nul 2>&1 || (echo [HATA] OpenSSH bulunamadi. Windows Ozellikleri > OpenSSH Client etkinlestirin.& pause & exit /b 1)
echo [ZK] Zamanlanmis gorev kuruluyor: ZK-EXE-windows_exe_ajan
schtasks /Create /TN "ZK-EXE-windows_exe_ajan" /TR "\"%~dp0zk_windows_exe_ajan.exe\"" /SC ONLOGON /RL HIGHEST /F
if %errorlevel% neq 0 (
    echo [HATA] Gorev kurulamadi. Bu dosyayi Yonetici olarak calistirin.
    pause
    exit /b 1
)
echo [ZK] Gorev baslatiliyor...
schtasks /Run /TN "ZK-EXE-windows_exe_ajan"
echo [ZK] Kurulum tamamlandi.
pause
