call venv_setup.bat
py -3.8 -m venv %venvdir%
call %venvdir%\scripts\activate.bat
REM python -m pip install -r requirements.txt