import sys, os
import platform
import traceback
import time
import argparse
from pathlib import Path

from .interactive import interact
from . import workspace, manager, using, using_top, use

from .__version__ import VERSION, VERSION_INFO

modname = '.'.join(globals()['__name__'].split('.')[:-1])
PATH_SEPERATOR = ';' if sys.platform == 'win32' else ':'

HEADER = f"""Live Scripting Environment {VERSION_INFO}
==================================="""
    
epilog = f"""Searchpaths
-----------
    The list of absolute paths is available as {modname}.manager.path
    
Configuring the searchpaths:
~~~~~~~~~~~~~~~~~~~~~~~~~~~~    

{modname } optional argument -p PATH, --path PATH:
    PATH is '{PATH_SEPERATOR}'-separated list of directories
    If not given, environment variable LIVEPATH is used.

Use of system environment variable LIVEPATH:
    '{PATH_SEPERATOR}'-separated list of directories
    If not given, search for higher directiory containing __live__.py

From withon Python:    
    {modname}.manager.path.append_path(some_path)
    
Examples
--------
          
{modname} -u script arg1 arg2

            Execute '__main__' function of 'my_script.py' script file and use 
            'arg1' as first argument.
            
{modname} -u script.hello_world

            Execute the 'hello_world' function of 'script.py' script file.         
            
{modname} arg1 arg2

            Execute '__main__' function of '__live__.py' script file and use 
            2 arguments: 'arg1' and 'arg2'
            
{modname} -i -u script.hello_world

            Enter interative mode after executing script.hello_world()        
"""

   
def argparser():    
    parser = argparse.ArgumentParser(description=HEADER, prog=f'python -m {modname}', 
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog)        
        
    parser.add_argument("arguments", type=str, help="Arguments", nargs='*')
    
    parser.add_argument("-p", "--path", type=str,
        help=f"""'{PATH_SEPERATOR}'-separated list of directories prefixed to the default live search path. 
If not given, environment variable LIVEPATH is used. The list of absolute paths is available as {modname}.manager.path.""")    
        
    parser.add_argument("-u", "--using", help="Start the __main__ function from this live module", nargs=1)
    parser.add_argument("-l", "--list", help="List the available scripts", action='store_true')

    parser.add_argument("-i", "--interactive", help="Start Python interactive",  action='store_true')
    parser.add_argument("-k", "--keycomplete", help="Enable key completer in interactive mode",  action='store_true')
    
    return parser

def argexec():
    parser = argparser()   
    args = parser.parse_args()    
    
    # if len(sys.argv) <= 1:
        # parser.print_help()
    
    ws = workspace    
        
    live_paths = None
    
    if args.path:
        live_paths = args.path.split(PATH_SEPERATOR)
    elif 'LIVEPATH' in os.environ.keys():
        #This is automatic added by __init__
        pass
    else:
        print('No live search paths defined')        
        path = Path('.').absolute()
        depth = 20
        while True:
            try:
                for item in os.scandir(path):
                    if item.is_dir() and (path / item.path / '__live__.py').exists():
                        p = str(path / item.path)
                        print(f'Found {p} having __live__.py')
                        live_paths = [p]
                        break
            except:
                print(f'Could not scan {path}')
            if depth == 0 or path == path.parent:
                break
            path = path.parent
            depth -= 1

    if not live_paths is None:
        manager.path.clear()
        for path in live_paths:
            manager.append_path(path)
        
    if args.list:
        print('Available top level scripts:')
        print()
        for item in dir(using_top):
            print(f'  {item}')
        print()
               
    ws['using'] = using
    ws['use'] = use
    ws['__name__'] = '__main__'
    ws['__interactive__'] = True if args.interactive else False
    
    if args.using:
        use_name = args.using[0]
        if not '.' in use_name:
            func = eval(f'using_top.{use_name}.__main__')         
        else:
            func = eval(f'using_top.{use_name}')         
    else:
        try:
            func = eval(f'using_top.__live__.__main__')            
        except:
            func = None
            
    argv = args.arguments            

    if func is None:
        if len(sys.argv) <= 1:
            parser.print_help()        
        
    else:
        try:
            ws['__returned_value__'] = func(*argv)
        except:
            traceback.print_exc()            
      
    if ws['__interactive__'] or func is None:        
        banner = 'Type using.<TAB> to get a list of the top level scripts\n'
        banner += 'exit() to exit'
        completer = 'key' if args.keycomplete else 'standard'
        interact(ws, banner, completer=completer)
        
    return ws
        
    
