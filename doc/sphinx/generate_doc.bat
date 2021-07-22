REM SET PYTHONPATH=%~dp0\..\..

set doc_root=.
set code_source=..\..\gdesk

set doc_source=%doc_root%\source
set doc_html=%doc_root%\build\html

set pwd=%CD%
echo %doc_source%

sphinx-apidoc.exe --separate -f -o %doc_source% %code_source% > sphinx-apidoc.log 2>&1
sphinx-build.exe -E -v -b html -n %doc_source% %doc_html% > sphinx-build-html.log 2>&1


cd %pwd%

pause