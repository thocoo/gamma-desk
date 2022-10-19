REM token in $HOME/.pypirc
cd ..
py -3.8 -m twine upload --repository pypi --verbose dist/*0.4.1-*
pause