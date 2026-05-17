@echo off
echo Derleniyor...
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
if exist build\Release\zk_windows_exe_ajan.exe (
    echo BASARI: .exe hazirlandi.
    copy build\Release\zk_windows_exe_ajan.exe .
) else ( echo HATA: Derleme basarisiz. )
pause
