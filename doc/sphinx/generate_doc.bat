SET PYTHONPATH=%~dp0\..\..
SET PYTHONPATH=%PYTHONPATH%;%~dp0\..\..\..\..\image_sensor_specs\pypack

set sphinxdir=C:\tools\python\python36\scripts

set doc_root=.
set code_source=..

set doc_source=%doc_root%\source
set doc_html=%doc_root%\build\html

set pwd=%CD%
echo %doc_source%

%sphinxdir%\sphinx-apidoc.exe --separate -f -o %doc_source% %code_source% > sphinx-apidoc.log 2>&1
%sphinxdir%\sphinx-build.exe -E -b html -n %doc_source% %doc_html% > sphinx-build-html.log 2>&1


cd %pwd%

pause