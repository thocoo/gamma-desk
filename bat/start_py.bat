:: Start GDesk with a Python version supplied as first argument
::   on the command line.
:: If the second argument is 'test' then execute a self-test procedure.
:: Example:
:: start_py.bat 3.13 test
@echo OFF

set PYTHON_VERSION=%1
set TEST=%2

IF [%PYTHON_VERSION%] == [] GOTO NOT_SUPPLIED

FOR %%G IN ("3.8"
            "3.9"
            "3.10"
            "3.11"
            "3.12"
            "3.13"
            ) DO (
            IF /I "%PYTHON_VERSION%"=="%%~G" GOTO SUPPORTED
)

:NOT_SUPPLIED
echo Python version is not given; supply as first argument (e.g.: 3.13).
pause
GOTO :EOF

:NOT_SUPPORTED
echo Python version is not supported: '%PYTHON_VERSION%'
pause
GOTO :EOF

:SUPPORTED
cd ..
if /I "%TEST%" == "test" (
    uv run --python %PYTHON_VERSION% python -m gdesk -i .\test\setup\test_gdesk.py
) else (
    uv run --python %PYTHON_VERSION% python -m gdesk
)
GOTO :EOF
