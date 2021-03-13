set doc_root=..

set doc_html=%doc_root%\sphinx\build\html

set pwd=%CD%
echo %doc_source%

xcopy /y %doc_html%\* %doc_root%\html\*
xcopy /y %doc_html%\_images\* %doc_root%\html\_images\*
xcopy /y %doc_html%\_sources\* %doc_root%\html\_sources\*
xcopy /y %doc_html%\_static\* %doc_root%\html\_static\*

cd %pwd%