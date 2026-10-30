@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo === 1/5 Виртуальное окружение ===
if not exist .venv\Scripts\python.exe py -3 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt || goto :error

echo === 2/5 yt-dlp и FFmpeg в папку bin ===
python tools\fetch_binaries.py || goto :error

echo === 3/5 Иконка ===
python tools\make_icon.py || goto :error

echo === 4/5 PyInstaller (onedir) ===
pyinstaller --noconfirm --clean Zephyrus.spec || goto :error

echo === 5/5 Установщик Inno Setup ===
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" goto :iscc
echo Inno Setup 6 не найден. Откройте installer\Zephyrus.iss в Inno Setup и нажмите Compile (Ctrl+F9).
goto :done

:iscc
"%ISCC%" "installer\Zephyrus.iss" || goto :error

:done
echo.
echo Готово. Установщик: installer\Output\
exit /b 0

:error
echo.
echo Сборка прервана из-за ошибки.
exit /b 1
