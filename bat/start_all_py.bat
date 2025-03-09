:: Start GDesk with a all supported Python versions.
:: If the first argument is 'test' then execute a self-test procedure.
:: Example:
:: start_all_py.bat test
@echo OFF

set TEST=%1

FOR %%G IN ("3.8"
            "3.9"
            "3.10"
            "3.11"
            "3.12"
            "3.13"
            ) DO (
            IF /I "%PYTHON_VERSION%"=="%%~G" GOTO SUPPORTED
)

:SUPPORTED
cd ..
if /I "%TEST%" == "test" (
    uv run --python %PYTHON_VERSION% --extra pyside2 python -m gdesk -i .\test\setup\test_gdesk.py
    uv run --python %PYTHON_VERSION% --extra pyside6 python -m gdesk -i .\test\setup\test_gdesk.py
) else (
    uv run --python %PYTHON_VERSION% --extra pyside2 python -m gdesk
    uv run --python %PYTHON_VERSION% --extra pyside6 python -m gdesk
)
GOTO :EOF
