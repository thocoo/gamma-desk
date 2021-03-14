"""
Bench Eye interface to the DOS console
"""
import sys
import logging
import argparse

from . import __release__
from . import configure, config

logger = logging.getLogger(__name__)

boot_handler = logging.StreamHandler(sys.stdout)
boot_handler.set_name('boot')
logging.root.addHandler(boot_handler)


MODNAME = '.'.join(globals()['__name__'].split('.')[:-1])
PATH_SEPERATOR = ';' if sys.platform == 'win32' else ':'

HEADER = f"Bench Eye {__release__}"
HEADER += '\n' + len(HEADER) * '=' + '\n'

DOC_HTML = 'https://thocoo.github.io/benchy-doc/docs'

HEADER += DOC_HTML + '\n'

epilog = f"""\
Examples
--------
          
{MODNAME} -i init_file.py
{MODNAME} -c config_file.???   
"""

def argparser():    
    parser = argparse.ArgumentParser(description=HEADER, prog=f'python -m {MODNAME}', 
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=epilog)        

    parser.add_argument("-c", "--config_file", help="Use this configuration file")
    parser.add_argument("-i", "--init_file", help="Run this init file in console 1")
    parser.add_argument("-d", "--debug", action='store_true', help="Set logging level to debug")
    parser.add_argument("pictures", nargs='*', help="Image file to load")    

    return parser


def argexec(argv=None, **config_kwargs):    
    parser = argparser()
    args = parser.parse_args(argv)
    
    configure(**config_kwargs)
    
    #Configure has to be done before import other modules    
    from .core.shellmod import Shell
    shell = Shell()
    
    return shell
