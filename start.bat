@echo off
rem ============================================================================
rem  Double-click entry: start the ComfyUI Toolbox Web panel.
rem  Then open http://127.0.0.1:8189 in your browser.
rem  Keep this file ASCII-only (see run.bat for why).
rem ============================================================================
call "%~dp0run.bat" panel
echo.
echo [panel exited] press any key to close this window...
pause >nul
