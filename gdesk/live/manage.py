# This module contains a script manager which implements Matlab like live scripting
# Support call of scripts which can be automatic reloaded without leaving the Python interpreter
# The user can modify code in a script file
# These script files will be reloaded based on modify time stamps
# New compiled code is direct available in current Python process

import os, sys, traceback, time
from pathlib import Path
import functools
from enum import Enum

import logging

logger = logging.getLogger(__name__)

class UpdateFlag(Enum):
    DONE = 1
    MODIFIED = 2
    ENFORCE = 3

class LoadError(Enum):
    NONE = 1
    SUCCEED = 2
    SYNTAX = 3
    EXECUTE = 4


def show_syntax_error(writer_call):
    """Display the syntax error that just occurred."""
    type, value, tb = sys.exc_info()
    sys.last_type = type
    sys.last_value = value
    sys.last_traceback = tb

    lines = traceback.format_exception_only(type, value)
    writer_call(''.join(lines))


def show_traceback(writer_call):
    """Display the exception that just occurred."""
    try:
        type, value, tb = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb
        tblist = traceback.extract_tb(tb)
        del tblist[:1]
        lines = traceback.format_list(tblist)
        if lines:
            lines.insert(0, "Traceback (most recent call last):\n")
        lines.extend(traceback.format_exception_only(type, value))
    finally:
        tblist = tb = None

    writer_call(''.join(lines))
    

def markUpdateCall(scm, ls_code, attr, nested=False):
    func_for_doc = getattr(ls_code.workspace, attr)
    
    @functools.wraps(func_for_doc, ('__module__', '__name__', '__doc__'))
    def wrapped_caller(*args, **kwargs):
        if not nested:
            scm.mark_for_update()
        error = ls_code.check_for_update()
        func = getattr(ls_code.workspace, attr)
        
        return func(*args, **kwargs)     
        
    return wrapped_caller
    

class LiveScriptModule(object):
    def __init__(self, script_manager, path, top=False):
        object.__setattr__(self, '__script_manager__', script_manager)
        object.__setattr__(self, '__path__', path)
        object.__setattr__(self, '__top__', top)


    @property
    def __wrapped__(self):
        scm = self.__script_manager__
        if self.__top__:
            scm.mark_for_update()
        ls_code = scm.ls_codes[self.__path__]
        ls_code.check_for_update()
        return ls_code.workspace


    def __getattr__(self, attr):
        wrapped_attr = getattr(self.__wrapped__, attr)

        if callable(wrapped_attr):
            nested = not self.__top__
            return markUpdateCall(self.__script_manager__, self.__script_manager__.ls_codes[self.__path__], attr, nested=nested)
        else:
            return wrapped_attr


    def __setattr__(self, attr, value):
        setattr(self.__wrapped__, attr, value)


    def __dir__(self):
        return self.__wrapped__.__dir__()


    def __repr__(self):
        return f'<LiveScriptModule \'{self.__path__}\'>'


    def __call__(self, *args, **kwargs):
        call = getattr(self, 'call')
        return call(*args, **kwargs)


    @property
    def __doc__(self):
        return self.__wrapped__.__doc__

        
class LiveScriptTree(object):

    def __init__(self, script_manager, path, top=False, name=None):
        object.__setattr__(self, '__script_manager__', script_manager)
        object.__setattr__(self, '__path__', path)
        object.__setattr__(self, '__top__', top)
        object.__setattr__(self, '__name__', name)


    def __dir__(self):
        lst = []
        lst = list(self.__dict__.keys())
        lst.extend(list(type(self).__dict__.keys()))        
        node = self.__path__
        for file in node.glob('*'):
            lst.append(file.stem)
        return lst


    def __getattr__(self, attr):
        path = self.__path__ / attr        
        qualname = f'{self.__name__}.{attr}'
        return self.__script_manager__.using_path(path, top=self.__top__, name=qualname)        


    def __repr__(self):
        return f"<LiveScriptTree '{self.__path__}'>"            


class LiveScriptScan(object):
    def __init__(self, script_manager, top=False):
        object.__setattr__(self, '__script_manager__', script_manager)
        object.__setattr__(self, '__top__', top)
        object.__setattr__(self, '__name__', 'LiveScriptScan')

    def __dir__(self):
        lst = []
        lst = list(self.__dict__.keys())
        lst.extend(list(type(self).__dict__.keys()))        
        paths = self.__script_manager__.path
        for path in paths:            
            node = Path(path)
            for file in node.glob('*'):
                if file.is_dir():
                    lst.append(file.stem)
                elif file.suffix.lower() == '.py':
                    lst.append(file.stem)
                    
        return lst
        
    def __getattr__(self, attr):
        try:
            return self.__using__(attr)
        except KeyError:
            #Without this, Jypeter doesn't auto-complete
            #I don't know why            
            raise AttributeError(attr)      
        

    def __call__(self, modstr):
        return self.__using__(modstr)
    
    def __using__(self, modstr):    
        logger.debug(f'Calling {modstr}')
        
        if isinstance(self.__top__, str):
            top = sys._getframe(2).f_globals['__name__'] == self.__top__
        else:
            top = self.__top__
            
        return self.__script_manager__.using_modstr(modstr, top, back=3)
            
    def __repr__(self):
        return f"<LiveScriptScan '{self.__script_manager__.path}'>"       
            
            
class LsCode(object):        

    def __init__(self, script_manager, path, name=None):
        self.script_manager = script_manager
        self.path = path
        self.name = 'unknown' if name is None else name
        self.load_modify = -1
        self.code = None        
        self.workspace = None
        self.ask_refresh = UpdateFlag.DONE


    def check_for_update(self):
        ls_code = self
        logger.debug(f'Checking for update, mode={ls_code.ask_refresh}')
        loaderror = LoadError.NONE

        if ls_code.ask_refresh == UpdateFlag.DONE: return loaderror

        if ls_code.ask_refresh == UpdateFlag.ENFORCE or \
            ((ls_code.ask_refresh == UpdateFlag.MODIFIED) and (ls_code.is_modified())):
            loaderror = ls_code.load()

        if loaderror == LoadError.SUCCEED:
            ls_code.ask_refresh = UpdateFlag.DONE
            logger.debug(f'Updated {ls_code.path}')

        elif loaderror in [LoadError.SYNTAX, LoadError.EXECUTE]:
            logger.warning(f'Failed to update {ls_code.path}')
            logger.warning(f'Error code {updated}')

        else:
            ls_code.ask_refresh = UpdateFlag.DONE
                    
        return loaderror


    def modify_time(self):
        return os.path.getmtime(str(self.path))


    def is_modified(self):
        logger.debug(f'{self.load_modify} < {self.modify_time()}, loading')
        return self.load_modify < self.modify_time()


    def load(self):
        """Import Python file (from disk, compile and execute)"""
        self.code = None        
        self.workspace = None
            
        with open(str(self.path), 'r', encoding='utf-8') as fp:
            current_modify_stamp = self.modify_time()
            pycode = fp.read()            
            
            try:
                codeobj = compile(pycode, str(self.path), 'exec')
                self.code = codeobj

            except SyntaxError:
                show_syntax_error(self.script_manager.write_syntax_err)
                return LoadError.SYNTAX
                
        self.workspace = LsWorkspace(self, str(self.path), self.name) 
                
        try:
            exec(codeobj, self.workspace.__dict__, self.workspace.__dict__)
                    
        except:
            show_traceback(self.script_manager.write_error)
            return LoadError.EXECUTE
            
        self.load_modify =  current_modify_stamp       
        logger.debug(f'{self.path} loaded at {time.ctime(self.load_modify)}')
        return LoadError.NONE
        
        
class LsWorkspace(object):
    #Provide a namespace for each script file.
    def __init__(self, ls_code, file, name='unknown'):
        self.__file__ = file
        self.__ls_code__ = ls_code
        self.__name__ = name

        
class LiveScriptManager(object):

    def __init__(self, workspace=None):
        # Add the search paths to self.path
        if workspace is None:
            workspace = dict()
        self.path = []        
        self.ls_codes = dict()
        self.workspace = workspace
        self.verbose = 3


    def find_script(self, modstr='test'):
        """Search for the script in the path list.
        Return the found path.
        """
        modpath = modstr.replace('.', '/')
        
        result = []
        
        for path in self.path:
            #It is not sure every path exists
            path = Path(path).absolute()
            if (path / modpath).with_suffix('.py').exists():
                result.append(((path / modpath).with_suffix('.py'), 'file'))
            elif (path / modpath).is_dir():
                result.append(((path / modpath), 'dir'))
            
        if len(result) == 0:
            logger.error(f'Can not find the scripts path or file: {modstr}')
            raise KeyError(f'{modstr} not found')

        elif len(result) == 1:           
            return result[0]

        else:
            logger.warning(f'Multiple matches found for {modstr}')
            for path in result:
                logger.warning(str(path[0]))
            return result[0]

                
    def append_path(self, path, resolve=True):
        path = Path(path).absolute()
        if resolve:
            try:
                path = path.resolve()
            except:
                print(f'Script path {path} not found')
                path = None
                
        if path is not None and str(path) not in self.path:
            self.path.append(str(path))


    def load(self, path, name=None):
        self.ls_codes[str(path)] = LsCode(self, path, name)
        self.ls_codes[str(path)].load()


    def update_now(self, enforce=False):
        """
        Reload the scripts in memory.
        If not enforced, load only scripts with more recent timestamps
        """
        self.pop_missing_paths()
        
        for ls_code in self.ls_codes.values():
            if enforce or ls_code.is_modified():
                load_error = ls_code.load()


    def mark_for_update(self, enforce=False):
        """Mark all modules to check for update at next first check_for_update() per module"""
        logger.debug('Marking all modules for update')
        mark = UpdateFlag.ENFORCE if enforce else UpdateFlag.MODIFIED
        for ls_code in self.ls_codes.values():
            ls_code.ask_refresh = mark

        
    def using_modstr(self, modstr, top=False, back=1):
        """Load a script or make a ScriptTree.
        A ScripTree is used to link to a dir.
        The loading of a script is done at moment of attribute access.
        """           
        if modstr.startswith('.'):
            name = sys._getframe(back).f_globals.get('__name__')
            
            if name is None:
                raise ImportError('Could not determine current module name')            
                
            this_parts = name.split('.')
            mod_parts = modstr.split('.')
            relative_level = mod_parts.count('')                
            parts0 = this_parts[:-relative_level]
            parts1 = mod_parts[relative_level:]        
            modstr = '.'.join(parts0 + parts1)  
        
        path, stype = self.find_script(modstr)
        return self.using_path(path, stype, top, modstr)

        
    def using_path(self, path, stype=None, top=False, name=None):        
        if stype is None:
            if path.is_dir():
                stype = 'dir'
            else:
                path = path.with_suffix('.py')
                if not path.exists():
                    raise ImportError(f'LiveScript {path} not found')
                else:
                    stype = 'file'
            
        if str(path) in self.ls_codes.keys():
            return LiveScriptModule(self, str(path), top)            
            
        if stype == 'file':
            loaderror = self.load(path, name)
            return LiveScriptModule(self, str(path), top)            
            
        elif stype == 'dir':
            return LiveScriptTree(self, path, top, name)


    def write_error(self, text):
        sys.stderr.write(text)       


    def write_syntax_err(self, text):
        sys.stderr.write(text)
        
        
    def pop_missing_paths(self):        
        for k in list(self.ls_codes):
            if not self.ls_codes[k].path.exists():
                self.ls_codes.pop(k)
        
