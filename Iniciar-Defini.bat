@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Defini - Iniciador
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0iniciar-defini.ps1"
if errorlevel 1 (
  echo.
  echo El iniciador termino con errores. Revisa los mensajes anteriores.
  pause
)
