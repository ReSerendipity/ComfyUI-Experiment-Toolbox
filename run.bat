@echo off
rem ============================================================================
rem  ComfyUI Toolbox - command dispatcher
rem  NOTE: keep this file ASCII-only. cmd.exe reads .bat in the OEM codepage,
rem        so non-ASCII here would be garbled. Chinese lives in run.py (UTF-8).
rem
rem  Usage:
rem    run.bat                  show entry list
rem    run.bat panel            start the Web panel (http://127.0.0.1:8189)
rem    run.bat sigma            offline sigma risk matrix
rem    run.bat unify [--apply]  unify prompt/seed
rem    run.bat models           cross-model controlled run
rem    run.bat analyze          result analysis
rem    run.bat pipeline         run step 1-4 in order
rem ============================================================================
setlocal

rem Switch the console to UTF-8 so redirected output matches run.py's UTF-8 stdout.
rem (A real console already renders CJK correctly; this fixes `run.bat ... > log.txt`.)
chcp 65001 >nul

rem --- ComfyUI bundled python (change here if your ComfyUI lives elsewhere) ---
set "PY=%USERPROFILE%\APP\ComfyUI-aki-v3\python\python.exe"

if not exist "%PY%" (
  echo [ERROR] ComfyUI python not found:
  echo         %PY%
  echo         Edit run.bat and point PY to your ComfyUI python.exe
  endlocal & exit /b 1
)

rem %~dp0 is this script's own folder (the toolbox root) - no hardcoded path needed
"%PY%" "%~dp0run.py" %*

rem Propagate run.py's exit code. A bare `endlocal` here would reset ERRORLEVEL to 0,
rem so capture it first and exit on a single line (%RC% expands before endlocal runs).
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
