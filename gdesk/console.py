"""
Bench Eye interface to the DOS console
"""
import sys
import logging
import argparse

from . import __release__, refer_shell_instance
from . import configure, config, doc_html
from .core import conf

logger = logging.getLogger(__name__)

boot_handler = logging.StreamHandler(sys.stdout)
boot_handler.set_name('boot')
logging.root.addHandler(boot_handler)


MODNAME = '.'.join(globals()['__name__'].split('.')[:-1])
PATH_SEPERATOR = ';' if sys.platform == 'win32' else ':'

HEADER = f"Bench Eye {__release__}"
HEADER += '\n' + len(HEADER) * '=' + '\n'

HEADER += doc_html + '\n'

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
    
    if args.debug:
        config_kwargs['logging_level'] = 'DEBUG'
        logging.root.setLevel(config_kwargs['logging_level'])      
    
    config_kwargs['qapp'] = True
    
    if args.config_file:
        config_kwargs['config_file'] = args.config_file

    if args.init_file:
        config_kwargs['init_file'] = args.init_file
        
    configure(**config_kwargs)        
    
    # Configure has to be done before import other modules    
    from .core.shellmod import Shell
    shell = Shell()
    refer_shell_instance(shell)
    
    from .gcore.guiapp import eventloop           
    eventloop(shell, init_file=config['init_file'], pictures=args.pictures)
    
    return shell
 
            
def run_as_child(console_args, config_kwargs, config_objects):    
    
    #Note that auto unpickling of received arguments can have caused a configarion to be execed
    #The configuration was triggered by the Process code on decode this function pointer    
    conf.config_objects.update(config_objects)
    
    #Allow reconfiguring
    conf.config.clear()
    conf.configured = False
    
    print(config_kwargs)
    
    argexec(console_args, **config_kwargs)

    
def is_imported_by_child_process():
    frame = sys._getframe()
    
    while not frame is None:
        module_name = frame.f_globals['__name__']
        if module_name == 'multiprocessing.spawn':
            return True
        frame = frame.f_back    
        
    return False    
    
    
if is_imported_by_child_process():
    configure(qapp=True)    