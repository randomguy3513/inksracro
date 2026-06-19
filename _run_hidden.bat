@echo off
cd /d "%~dp0"
set "PYW=pythonw"
where pythonw >nul 2>&1 || set "PYW=pyw"
%PYW% "%~dp0mining_macro.py"
