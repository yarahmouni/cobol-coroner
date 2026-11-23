@echo off
rem Windows launcher of scripts/kiro-hook: runs the Python interpreter of the repository
rem virtual environment with the given arguments. The environment is found from the location
rem of this file, not from the current directory. Arguments and standard input go to Python.
rem With no virtual environment it prints one line on stderr and exits 1. Exit 1 is not a block
rem (a block is exit 2 with a JSON decision), which is what coroner.hooks does when its own
rem scope or certificate lookup fails: it allows.
setlocal
set "PYTHON=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" goto missing
"%PYTHON%" %*
exit /b %ERRORLEVEL%
:missing
>&2 echo kiro-hook: no virtual environment at %~dp0..\.venv; run: py -3.12 -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev]"
exit /b 1
