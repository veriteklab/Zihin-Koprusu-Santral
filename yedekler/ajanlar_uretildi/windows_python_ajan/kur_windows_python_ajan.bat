@echo off
setlocal
cd /d "%~dp0"
echo [ZK] Windows SSH ajan kurulumu - Windows Python Ajan
python --version >nul 2>&1 || (echo [HATA] Python bulunamadi. https://python.org adresinden indirin.& pause & exit /b 1)
where ssh >nul 2>&1 || (echo [HATA] OpenSSH bulunamadi. Windows Ozellikleri > OpenSSH Client etkinlestirin.& pause & exit /b 1)
echo [*] Tor Browser veya Expert Bundle calisiyor mu kontrol ediliyor...
echo [!] Eger Tor calismiyorsa lutfen Tor Browser'i acin veya:
echo     https://www.torproject.org/download/tor/ adresinden Expert Bundle indirin.
echo.
echo [ZK] Zamanlanmis gorev kuruluyor: ZK-SSH-windows_python_ajan
schtasks /Create /TN "ZK-SSH-windows_python_ajan" /TR "python \"%~dp0zk_windows_python_ajan.py\"" /SC ONLOGON /RL HIGHEST /F
if %errorlevel% neq 0 (
    echo [HATA] Gorev kurulamadi. Bu dosyayi Yonetici olarak calistirin.
    pause
    exit /b 1
)
echo [ZK] Gorev baslatiliyor...
schtasks /Run /TN "ZK-SSH-windows_python_ajan"
echo [ZK] Kurulum tamamlandi.
pause
