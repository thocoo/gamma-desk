import os, sys
import time
import collections
from pathlib import Path
import pprint
import json
import importlib
import copy
import re

import logging

logger = logging.getLogger(__name__)

global config

config = dict()
config_objects = dict()
configured = False

here = Path(__file__).parent.absolute()

FIRST_CONFIG_FILE = here.parent / 'config' / 'defaults.json'

REQUIRED = [
    ('numpy', 'numpy'),
    ('matplotlib', 'matplotlib'),
    ('PySide2', 'PySide2'),
    ('qtpy', 'qtpy'),
    ('psutil', 'psutil'),
    ('numba', 'numba'),
    ('pyzmq', 'zmq'),
    ('benchy', 'benchy'),
]

PATHPATTERN = re.compile('path_\w*')

def deep_update(source, overrides):
    """
    Update a nested dictionary or similar mapping.
    Modify ``source`` in place.
    """
    for key, value in overrides.items():
        if isinstance(value, collections.Mapping) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:            
            source[key] = overrides[key]
            if PATHPATTERN.match(str(key)) or key in ['respath']:
                if not source[key] is None:
                    source[key] = os.path.expandvars(source[key])
    return source             
    
def deep_diff(dict1, dict2):
    """
    Difference of nested dictionary or similar mapping.
    """    
    common_keys = set(dict1.keys()).intersection(set(dict2.keys()))    
    dict1_keys_only = set(dict1.keys()).difference(set(dict2.keys()))
    dict2_keys_only = set(dict2.keys()).difference(set(dict1.keys()))
    
    result = dict((key, dict2[key]) for key in dict2_keys_only)
    
    for key in common_keys:
        value1 = dict1[key]
        value2 = dict2[key]
        if isinstance(value1, collections.Mapping):
            assert isinstance(value2, collections.Mapping)
            value = deep_diff(value1, value2) 
            if len(value) > 0:
                result[key] = value
        elif value1 !=  value2:
            result[key] = value2
            
    return result       
            
def list_packages(packages):
    for (package, base) in packages:
        found = importlib.util.find_spec(base)
        if found is None:
            logger.debug(f'{package}:\n    NOT FOUND')
        else:
            modified = os.path.getmtime(found.origin)
            modified_str = time.strftime('%Y-%b-%d %H:%M:%S',time.gmtime(modified))
            origin = Path(found.origin)
            install_dir = origin.parent.parent
            logger.debug(f'{package}:\n    {origin.parent}\n    {origin.name}: {modified_str}')
            for path in install_dir.glob(f'{package}*.dist-info'):
                logger.debug(f'    dist-info: {path.stem}')    
                
def configure(**overwrites):
    global configured        
    
    if configured:
        name = sys._getframe(1).f_globals['__name__']
        if not name in ['ghawk2.core.tasks']:
            logging.warning(f'configure unexpected called from {name} but already configured, no reconfiguring done')
        return
    else:    
        configured = True
    
    os.environ['BENCHYROOT'] = str(here.parent.absolute())
    
    config_file = FIRST_CONFIG_FILE   
    deep_update(config, load_config(config_file))
    
    prior_config_file = None    
    next_config_file = overwrites.get('config_file', None) or config['next_config_file'] 
    
    while not next_config_file is None:
        config_file = Path(next_config_file).expanduser()       
        if not config_file.exists(): break 
        if prior_config_file == config_file:
            logger.warn(f'config file {config_file} is loading itself')
            break
        logger.info(f'Loading config: {config_file}')
        deep_update(config, load_config(config_file))        
        prior_config_file = config_file
        next_config_file = config['next_config_file']
    
    deep_update(config, overwrites)   
    
    os.environ['QT_API'] = config['qt_api']
    logging.root.setLevel(config['logging_level'])
    
    if config['debug'].get('list_packages', False):
        list_packages(REQUIRED)   
    
    #TO DO: import register_objects_in_ghawk2_init
    #from ghawk2.core.gui_proxy import register_objects_in_ghawk2_init
    #register_objects_in_ghawk2_init()
    
    #TO DO: Configure Matplotlib
    # Importing matplotlib takes some time !
    # It also imports numpy
    import matplotlib
    #matplotlib.use(config['matplotlib']['backend'])
    
    #Configure plugins
    #import ghawk2.panels.dialog
    #import ghawk2.panels.stdio
    #import ghawk2.panels.imgview
    #import ghawk2.panels.matplot
    #import ghawk2.panels.levels
    #import ghawk2.panels.values    
    
    for panel_class_module in config["panel_class_modules"]:
        exec(f'import {panel_class_module}')
    
def save_config_json(path=None):
    current_config = copy.deepcopy(config)
    current_config['qapp'] = False
    current_config['next_config_file'] = None
    save_config = not_defaults(current_config)
    with open(path, 'w') as fp:
        json.dump(save_config, fp, indent=2)
        
def load_config(path):
    config_file = Path(path)
    
    if config_file.suffix in ['.cpy']:
        config_dict = eval(open(config_file).read())
        
    elif config_file.suffix in ['.json']:
        config_dict = load_config_json(config_file)
        
    return config_dict
        
def load_config_json(path=None):
    with open(path, 'r') as fp:
        loaded_config = json.load(fp)        
    return loaded_config

def not_defaults(current_config):
    defaults = {}    
    deep_update(defaults, load_config(FIRST_CONFIG_FILE))
    return deep_diff(defaults, current_config)
    