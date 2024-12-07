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
    

def markUpdateCall(scm, module, attr, nested=False):
    func_for_doc = getattr(module.workspace, attr)
    
    @functools.wraps(func_for_doc, ('__module__', '__name__', '__doc__'))
    def wrapped_caller(*args, **kwargs):
        if not nested:
            scm.mark_for_update()
        error = module.check_for_update()
        func = getattr(module.workspace, attr)
        
        return func(*args, **kwargs)     
        
    return wrapped_caller
    

class LiveScriptModuleReference(object):
    """"For every reference to a module, a dedicated LiveScriptModuleReference is created
    This is mainly to store it's top attribute. Which can differ between the references
    """

    def __init__(self, script_manager, path, top=False, modstr=None):
        object.__setattr__(self, '__script_manager__', script_manager)
        object.__setattr__(self, '__path__', path)
        object.__setattr__(self, '__modstr__', modstr)
        object.__setattr__(self, '__top__', top)


    @property
    def __wrapped__(self):
        scm = self.__script_manager__
        if self.__top__:
            scm.mark_for_update()
        module = scm.modules[self.__modstr__]
        module.check_for_update()
        return module.workspace


    def __getattr__(self, attr):
        wrapped_attr = getattr(self.__wrapped__, attr)

        if callable(wrapped_attr):
            nested = not self.__top__
            return markUpdateCall(self.__script_manager__, self.__script_manager__.modules[self.__modstr__], attr, nested=nested)
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


class LiveScriptModule(object):

    def __init__(self, script_manager, path, name=None):
        self.script_manager = script_manager
        self.path = path
        self.name = 'unknown' if name is None else name
        self.load_modify = -1
        self.code = None
        self.workspace = None
        self.ask_refresh = UpdateFlag.DONE

    def check_for_update(self):
        logger.debug(f'Checking for update, mode={self.ask_refresh}')
        loaderror = LoadError.NONE

        if self.ask_refresh == UpdateFlag.DONE: return loaderror

        if self.ask_refresh == UpdateFlag.ENFORCE or \
                ((self.ask_refresh == UpdateFlag.MODIFIED) and (self.is_modified())):
            loaderror = self.load()

        if loaderror == LoadError.SUCCEED:
            self.ask_refresh = UpdateFlag.DONE
            logger.debug(f'Updated {self.path}')

        elif loaderror in [LoadError.SYNTAX, LoadError.EXECUTE]:
            logger.warning(f'Failed to update {self.path}')
            logger.warning(f'Error code {updated}')

        else:
            self.ask_refresh = UpdateFlag.DONE

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

        self.workspace = LsWorkspace(self, str(self.path), self.name, self.script_manager)

        try:
            exec(codeobj, self.workspace.__dict__, self.workspace.__dict__)

        except:
            show_traceback(self.script_manager.write_error)
            return LoadError.EXECUTE

        self.load_modify = current_modify_stamp
        logger.debug(f'{self.path} loaded at {time.ctime(self.load_modify)}')
        return LoadError.NONE


class LsWorkspace(object):
    #Provide a namespace for each script file.
    def __init__(self, module, file, name, scm):
        self.__file__ = file
        self.__module__ = module
        self.__name__ = name
        self.__loader__ = scm

        
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
        return self.__script_manager__.using_path(path, top=self.__top__, modstr=qualname)


    def __repr__(self):
        return f"<LiveScriptTree '{self.__path__}'>"            


class LiveScriptScan(object):
    """The root object to scan through the scripts (use or using)
    Only scripts which are called by another script or the root are loaded.
    So other script which are not loaded are allowed having syntax or execution errors.
    """

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

        
class LiveScriptManager(object):

    def __init__(self, workspace=None):
        # Add the search paths to self.path
        self.path = []

        #The loaded modules
        self.modules = dict()


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


    def load(self, path, modstr=None):
        module = LiveScriptModule(self, path, modstr)
        self.modules[modstr] = module
        module.load()


    def update_now(self, enforce=False):
        """
        Reload the scripts in memory.
        If not enforced, load only scripts with more recent timestamps
        """
        self.pop_missing_paths()
        
        for module in self.modules.values():
            if enforce or module.is_modified():
                load_error = module.load()


    def mark_for_update(self, enforce=False):
        """Mark all modules to check for update at next first check_for_update() per module"""
        logger.debug('Marking all modules for update')
        mark = UpdateFlag.ENFORCE if enforce else UpdateFlag.MODIFIED
        for module in self.modules.values():
            module.ask_refresh = mark

        
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


    def using_path(self, path, stype=None, top=False, modstr=None):
        if stype is None:
            if path.is_dir():
                stype = 'dir'
            else:
                path = path.with_suffix('.py')
                if not path.exists():
                    raise ImportError(f'LiveScript {path} not found')
                else:
                    stype = 'file'
            
        if modstr in self.modules.keys():
            return LiveScriptModuleReference(self, str(path), top, modstr)
            
        if stype == 'file':
            loaderror = self.load(path, modstr)
            return LiveScriptModuleReference(self, str(path), top, modstr)
            
        elif stype == 'dir':
            return LiveScriptTree(self, path, top, modstr)


    def write_error(self, text):
        sys.stderr.write(text)       


    def write_syntax_err(self, text):
        sys.stderr.write(text)
        
        
    def pop_missing_paths(self):        
        for k in list(self.modules):
            if not self.modules[k].path.exists():
                self.modules.pop(k)
        
