REM token in $HOME/.pypirc
cd ..
python -m twine upload --verbose dist/*
pause