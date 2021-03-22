SET VENV_PY_VERSION =-3.8
SET VENV_NAME=py38

REM Check if the venv is there and create it if not
if not exist .\venv\%VENV_NAME%\Scripts\activate.bat (
    echo Virtual environment %VENV_NAME% not yet there, creating it.
    py.exe %VENV_PY_VERSION% -m venv venv\%VENV_NAME%
    echo Activating the venv
    call venv\%VENV_NAME%\Scripts\activate.bat
    echo Installing all packages from requirements.txt
    venv\%VENV_NAME%\Scripts\python.exe -m pip install -r .\setup\requirements.txt
)

REM Make sure pip-sync is there
if not exist .\venv\%VENV_NAME%\Scripts\pip-sync.exe (
    venv\%VENV_NAME%\Scripts\python.exe -m pip install -r .\setup\requirements.txt
)
echo Run pip-sync to make sure the venv is in line with .\setup\requirements.txt
venv\%VENV_NAME%\Scripts\python.exe -m piptools sync .\setup\requirements.txt

pause
