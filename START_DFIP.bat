@echo off
cd /d "%~dp0"
py main.py
if errorlevel 1 (
 echo.
 echo Trying python command...
 python main.py
)
if errorlevel 1 pause
