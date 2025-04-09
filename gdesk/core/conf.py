import os
import sys
import time
from collections.abc import Mapping
from pathlib import Path
import json
import importlib
import importlib.util
import copy
import re
import logging

logger = logging.getLogger(__name__)

global config

config = dict()
config_objects = dict()
configured = False

here = Path(__file__).parent.absolute()

if sys.platform == 'win32':
    FIRST_CONFIG_FILE = here.parent / 'config' / 'defaults.json'
elif sys.platform in ('linux', 'darwin'):
    FIRST_CONFIG_FILE = here.parent / 'config' / 'defaults_unix.json'
else:
    ImportError(f'platfrom {sys.platform()} not supported')

REQUIRED = [
    ('numpy', 'numpy'),
    ('matplotlib', 'matplotlib'),
    ('PySide2', 'PySide2'),
    ('PySide6', 'PySide6'),
    ('PyQt5', 'PyQt5'),
    ('PyQt6', 'PyQt6'),
    ('qtpy', 'qtpy'),
    ('psutil', 'psutil'),
    ('numba', 'numba'),
    ('pyzmq', 'zmq'),
    ('gdesk', 'gdesk'),
]

PATHPATTERN = re.compile(r'path_\w*')


def deep_update(source, overrides):
    """
    Update a nested dictionary or similar mapping.
    Modify ``source`` in place.
    """
    for key, value in overrides.items():
        if isinstance(value, Mapping) and value:
            returned = deep_update(source.get(key, {}), value)
            source[key] = returned
        else:
            source[key] = overrides[key]
            if PATHPATTERN.match(str(key)) or key in ['respath']:
                if not source[key] is None:
                    if isinstance(source[key], list):
                        source[key] = [os.path.expandvars(val) for val in source[key]]
                    else:
                        source[key] = os.path.expandvars(source[key])
    return source

def deep_diff(dict1, dict2):
    """
    Difference of nested dictionary or similar mapping.
    """
    common_keys = set(dict1.keys()).intersection(set(dict2.keys()))
    dict2_keys_only = set(dict2.keys()).difference(set(dict1.keys()))

    result = dict((key, dict2[key]) for key in dict2_keys_only)

    for key in common_keys:
        value1 = dict1[key]
        value2 = dict2[key]
        if isinstance(value1, Mapping):
            assert isinstance(value2, Mapping)
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
        if not name in ['gdesk.core.tasks']:
            logging.warning(f'configure unexpected called from {name} but already configured, no reconfiguring done')
        return
    else:
        configured = True

    os.environ['GDESKROOT'] = str(here.parent.absolute())    

    config_file = FIRST_CONFIG_FILE
    print(f'Loading config: {config_file}')
    deep_update(config, load_config(config_file))

    prior_config_file = None
    config_files = overwrites.get('path_config_files', None) or config.get('path_config_files', [])
    #if not isinstance(config_files, list): config_files = [config_files]
    
    while len(config_files) > 0:
        print(f'config_files: {config_files}')
        next_config_file = config_files.pop(0)
        config_file = Path(next_config_file).expanduser()
        if not config_file.exists():
            logger.warn(f'Configfile not found: {config_file}')
            continue        
        print(f'Loading config: {config_file}')
        deep_update(config, load_config(config_file))
        prior_config_file = config_file
        config_files = config.get('path_config_files', [])

    deep_update(config, overwrites)
    
    if not 'QT_ENABLE_HIGHDPI_SCALING' in os.environ:    
        os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1' if config.get('high_dpiscaling', False) else '0'
    
    if 'QT_API' in os.environ.keys():
        pass
    
    elif 'qt_api' in config.keys():
        print('Configuring PySide version by the config json')
        os.environ['QT_API'] = config['qt_api']        
        os.environ['FORCE_QT_API'] = '1'        
        
    else:
        for i in range(1):
            try:
                import PySide6
                break
            except ImportError:
                logger.warn('Could not import PySide6, trying PySide2')
            
            try:
                import PySide2         
                break
            except ImportError:
                raise ImportError('Install either PySide2 or PySide6 by pip install pyside2 or pip install pyside6')

    logging.root.setLevel(config['logging_level'])    

    if config['debug'].get('list_packages', False):
        list_packages(REQUIRED)

    # Error log folder: use current work dir *or* override through
    # configuration value 'path_errorlog'.
    error_log_dir = config.get('path_errorlog') or Path.cwd()
    error_log_dir = Path(error_log_dir).expanduser()
    config["path_errorlog"] = error_log_dir

    from gdesk import refer_gui_instance
    from .gui_proxy import gui
    refer_gui_instance(gui)                     

    #TO DO: import register_objects_in_gdesk_init
    #from gdesk.core.gui_proxy import register_objects_in_gdesk_init
    #register_objects_in_gdesk_init()
    config_matplotlib()      
    
    #Configure and register plugins
    for panel_class_module in config["panel_class_modules"]:
        exec(f'import {panel_class_module}')
        
        
def config_matplotlib():
    # Importing matplotlib takes some time !
    # It also imports numpy
    import matplotlib
    matplotlib.use(config['matplotlib']['backend'])
    #This will also call the backend module
    #Which import ..panels.matplot
    import pylab
    

def save_config_json(path=None):
    current_config = copy.deepcopy(config)
    current_config['qapp'] = False
    current_config['next_config_file'] = None
    save_config = not_defaults(current_config)
    save_config = stringify_paths(save_config)
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


def stringify_paths(current_config: dict) -> dict:
    """Return a copy of the dict with all Path instances converted to strings."""
    config_copy = {}

    for key, value in current_config.items():
        if isinstance(value, dict):
            # Recurse.
            config_copy[key] = stringify_paths(value)
        elif isinstance(value, Path):
            config_copy[key] = str(value)
        else:
            config_copy[key] = copy.deepcopy(value)

    return config_copy
