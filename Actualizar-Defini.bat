@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Defini - Actualizar dependencias
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-defini.ps1" -SoloActualizar
echo.
pause
