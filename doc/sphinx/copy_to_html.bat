set doc_root=..

set doc_src_html=%doc_root%\sphinx\build\html
set doc_tgt_html=%doc_root%\..\..\benchy-doc\docs

set pwd=%CD%

xcopy /y %doc_src_html%\* %doc_tgt_html%\*
xcopy /y %doc_src_html%\_images\* %doc_tgt_html%\_images\*
xcopy /y %doc_src_html%\_sources\* %doc_tgt_html%\_sources\*
xcopy /y %doc_src_html%\_static\* %doc_tgt_html%\_static\*

cd %pwd%
pause