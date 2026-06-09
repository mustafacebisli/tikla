@echo off
python -m pip install -r requirements.txt
python -m PyInstaller --onefile --windowed --name "SagTik" right_clicker.py
echo.
echo Exe hazir: dist\SagTik.exe
pause
