REM token in $HOME/.pypirc
cd ..
py -3.8 -m twine upload --repository pypi --verbose dist/*1.6.0-*

:: Note: alternative using UV, requires custom configuration.
:: See https://docs.astral.sh/uv/guides/package/#publishing-your-package
:: uv publish --index pypi
pause