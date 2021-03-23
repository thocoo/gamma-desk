"""The is the doctring of live.
Example of nested live script

-- scripts/info.py ---------------------

 def get_info():
     return f'Info from {__file__}'

----------------------------------------

-- scripts/map1/hello.py ---------------

 from gdesk.live import using
 info = using.info

 def hello_world():
     print(f'Hello world')
     print(info.get_info())

----------------------------------------

-- Use of using at top level -----------

 from gdesk.live import manager, use
 manager.append_path('scripts')
 hello = use.map1.hello
 hello.hello_world() 
"""

import sys
import os

from .manage import LiveScriptManager, LiveScriptScan

workspace = dict()

manager = LiveScriptManager(workspace)        

PATH_SEPERATOR = ';' if sys.platform == 'win32' else ':'

if 'LIVEPATH' in os.environ.keys():
    for path in os.environ['LIVEPATH'].split(PATH_SEPERATOR):
        manager.append_path(path)

using = LiveScriptScan(manager, top='__main__')  #Become top if current workspace name is __main__
using_sub = LiveScriptScan(manager, top=False)
use = using_top = LiveScriptScan(manager, top=True)