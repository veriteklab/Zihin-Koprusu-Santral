@echo off
setlocal
cd /d "%~dp0"
echo [ZK] HTTP ajan kurulumu - Windows HTTP Ajan
python --version >nul 2>&1 || (echo [HATA] Python bulunamadi.& pause & exit /b 1)
echo [ZK] Zamanlanmis gorev kuruluyor: ZK-HTTP-windows_http_ajan
schtasks /Create /TN "ZK-HTTP-windows_http_ajan" /TR "python \"%~dp0zk_windows_http_ajan_http.py\"" /SC ONLOGON /RL HIGHEST /F
if %errorlevel% neq 0 (
    echo [HATA] Gorev kurulamadi. Bu dosyayi Yonetici olarak calistirin.
    pause
    exit /b 1
)
echo [ZK] Gorev baslatiliyor...
schtasks /Run /TN "ZK-HTTP-windows_http_ajan"
echo [ZK] Kurulum tamamlandi.
pause
