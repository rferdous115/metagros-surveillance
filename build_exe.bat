@echo off
echo Building Metagros EXE...

REM Clean previous builds
rmdir /s /q build
rmdir /s /q dist
del *.spec

REM Run PyInstaller
REM --onefile: Bundles everything into a single .exe
REM --noconsole: Hides the terminal window (optional, but good for GUI apps)
REM --name: Application name
REM --add-data: Include necessary data files

pyinstaller --noconsole --onefile --clean ^
    --name Metagros ^
    --add-data "yolov8n.pt;." ^
    --hidden-import win10toast ^
    --hidden-import qtawesome ^
    --hidden-import ultralytics ^
    --hidden-import engineio.async_drivers.threading ^
    qt_app.py

echo Build complete! Check 'dist' folder.
pause
