import sys
import os
import threading
import multiprocessing
import builtins
import logging
import traceback
import queue
import subprocess
import pprint
import shlex
import json
import psutil
import inspect
from pathlib import Path
from itertools import islice

from . import stdinout
from .interpreter import QueueInterpreter
from .stdinout import ProcessStdInput
from .gui_proxy import gui
from .conf import config
from .history import LogDir
   
from ..utils.names import DictStruct 
from ..rectable import RecordTable
from ..live import use, manager
from ..live.manage import LiveScriptModuleReference

from rlcompleter import Completer
from ..live.completer import Completer as LiveCompleter

COMPLETER = config.get('console', {}).get('completer', 'native')      
MULTIKEY =  config.get('console', {}).get('multikey', False)

here = Path(__file__).absolute().parent
logger = logging.getLogger(__name__) 
  
class Shell(object):
    instance = None
    
    def __init__(self, workspace=None, redirect=True, logdir=True):
        self.wsdict = dict() if workspace is None else workspace
        self.ws = DictStruct(self.wsdict)
             
        Shell.instance = self
        self.wsdict['shell'] = self        
        self.wsdict['gui'] = gui
        self.wsdict['use'] = use     
        self.wsdict['__name__'] = '__main__'        
        
        if redirect:
            self.redirect_stdout()            
            self.redirect_input()
        
        if COMPLETER == 'native':
            self.comp = Completer(self.wsdict)
        else:
            self.comp = LiveCompleter(self.wsdict, multikey=MULTIKEY)
            
        self.interpreters = dict()
        
        if logdir:
            self.logdir = LogDir(config['path_log'])
            
        self.bootpath = Path('.').resolve()
        
    def redirect_stdout(self):
        if not config['debug']['skip_main_stdout_redirect']:
            current_stdout = sys.stdout
            sys.stdout = self.stdout = stdinout.StdOutRouter()
            sys.stdout.backup_stream = current_stdout
            stdinout.enable_ghstream_handler()
            
        if not config['debug']['skip_main_stderr_redirect']:
            current_stderr = sys.stderr
            sys.stderr = self.stderr = stdinout.StdErrRouter()
            sys.stderr.backup_stream = current_stderr
            
    def get_watcher_ports(self):
        lock_files = self.logdir.get_active_lock_files()
        lock_files = sorted(lock_files, key=os.path.getmtime)
        ports = []
        
        for lock_file in lock_files:
            info_file = lock_file.parent / 'cmdserver.json'
            if not info_file.exists(): continue
            with open(str(info_file), 'r') as fp:
                content = json.load(fp)
            ports.append(content['port'])

        return ports

    @property
    def _qapp(self):
        from qtpy.QtWidgets import QApplication
        return QApplication.instance()
            
    def redirect_input(self):        
        #ProcessStdInput is missing some function
        #to be a good overwrite of sys.stdin. But it is not needed to overwrite sys.stdin
        #Only, overwriting builtins.input is good enough
        #(original input function doesn't seem to be compatible with ProcessStdInput)
        self.stdin = ProcessStdInput()                   
        self.__input__ = builtins.input           
        builtins.input = self.input     
        sys.displayhook = sys.__displayhook__

    def restore_stdout(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        #The following is used to customize the repr functionaility
        #It also stores to _
        sys.displayhook = sys.__displayhook__ 
        
    def restore_input(self):
        builtins.input = self.__input__
        
    def info(self):
        """
        Print info about the current process
        """
        prc = psutil.Process(os.getpid())
        pyprc = multiprocessing.current_process()
        print(f'name: {prc.name()}')
        print(f'pname: {pyprc.name}')
        print(f'exe: {prc.exe()}')
        print(f'argv: {sys.argv}')
        print(f'cwd: {prc.cwd()}')  
        print(f'pid: {prc.pid}')
        print(f'ppid: {prc.ppid()}')              
        print(f'mem rss: {prc.memory_info().rss}')
        print(f'#threads: {prc.num_threads()}')
        this_thread = threading.currentThread()
        print(f'thread name: {this_thread.name}')
        print(f'tid: {this_thread.ident}')
        print(self._qapp.cmdserver.host_info())
        
    def this_interpreter(self):
        """
        Return the interpreter related to this thread.
        """
        tid = threading.get_ident()
        #TO DO, support for other threads which are not in a console ?
        #       what about the stdout of these threads
        return self.interpreters.get(tid, None)
        
    def edit_file(self, filename, lineno=0):
        """
        Edit the file with an external editor at a certain lineno.        
        """
        editorExecutable = Path(config.get('texteditor', '.'))
        
        if not editorExecutable.exists():
            logger.warning(
                f"Text editor executable does not exist: '{editorExecutable}'."
                "\nAdd to your gdconf.json file file the key 'texteditor', with as value "
                " the full path to the executable."
            )
            editorExecutable = Path(os.path.expandvars(r'%WINDIR%\system32\notepad.exe'))
        
        if editorExecutable.name.lower() == 'notepad++.exe':
            # supply line number argument
            os.spawnl(os.P_NOWAIT, editorExecutable, '"' + str(editorExecutable) + '"', '-n%d'%lineno, '"{0}"'.format(filename))

        elif editorExecutable.name.lower() == 'code.exe':
            os.spawnl(os.P_NOWAIT, editorExecutable, '"' + str(editorExecutable) + '"',  '-g', f'"{filename}:{lineno}"')

        else:
            if sys.platform in ("linux", "darwin"):
                # Don't use quotes around the file name.
                os.spawnl(os.P_NOWAIT, editorExecutable, f'"{editorExecutable}"', filename)
            else:
                os.spawnl(os.P_NOWAIT, editorExecutable, '"' + str(editorExecutable) + '"', '"{0}"'.format(filename))

    def edit_dbase(self, filename):
        """
        Edit a SQLite file with an external editor.
        """
        executable = config['dbbrowser']
        os.spawnl(os.P_NOWAIT, executable, '"' + executable + '"', '"{0}"'.format(filename))        
        
    def edit(self, object):
        """
        Edit source file of object with external editor
        
        :param objects: object from which the source code will be opened in an editor
        :return: None
        """
        object_type_name = type(object).__name__
        
        if object_type_name == 'ImageDataManager':
            self.edit_dbase(object.fullpath)
            return
                    
        (filename, lineno) = self.getcodefile(object)
        
        if not filename is None:
            logger.info('opening "%s" with editor at line %d' % (filename, lineno))
            self.edit_file(filename, lineno)
            
        else:
            logger.warn('Could not find the file for object')
                
    def getcodefile(self, object):
        """
        Find out which source or compiled file an object was defined in.
        """
        
        fi = None
        lineno = 0
        
        if isinstance(object, LiveScriptModuleReference):
            fi = object.__file__
            return (fi, lineno)
                    
        if hasattr(object, '__wrapped__'):
            #Maybe wrapped by the functools.wraps decorator
            object = object.__wrapped__                
                            
        if hasattr(object, 'ls_code'):
            #it is a script callable
            code = object.func.__code__
            fi = code.co_filename
            lineno = code.co_firstlineno
            
        elif hasattr(object, '__func__'):
            code = object.__func__.__code__
            fi = code.co_filename
            lineno = code.co_firstlineno            
            
        else:
            
            try:
                fi = inspect.getsourcefile(object)
            except:
                fi = None
                
            if fi is None:
                fi = inspect.getsourcefile(type(object))                    
            
            if hasattr(object, '__code__'):
                try:
                    lineno = object.__code__.co_firstlineno
                except:
                    lineno = 1
            else:
                try:
                    lineno = inspect.getlineno(object)
                except AttributeError:
                    lineno = 1
                
        return (fi, lineno)                
                    
    @staticmethod
    def new_interactive_thread(cqs, guiproxy=None, client=True, console_id=None):
        shell = Shell.instance
        
        if client and type(cqs).__name__ == 'ZmqQueues':
            cqs.setup_as_client()
        
        thread = threading.Thread(target=QueueInterpreter.create_and_interact, args=(shell, cqs, guiproxy, console_id), name='Interact',daemon=True)
        thread.start()
        return (thread.name, thread.ident)
        
    def popen(self, commands, shell=True, stdin=True):        
        
        #https://eli.thegreenplace.net/2017/interacting-with-a-long-running-child-process-in-python/
        
        if isinstance(commands, str):
            commands = shlex.split(commands)
    
        def output_reader(proc):
            for line in iter(proc.stdout.readline, b''):
                sys.stdout.write(line.decode('utf-8'))
                sys.stdout.flush()
                
            print(f'{commands[0]}: stdout ended')
            #sys.stdout.redirects.pop(threading.get_ident())
            
        def stderr_reader(proc):
            for line in iter(lambda: proc.stderr.read(1), b''):
                sys.stderr.write(line.decode('utf-8'))
                sys.stderr.flush()
                
            print(f'{commands[0]}: stderr ended')
            #sys.stderr.redirects.pop(threading.get_ident())            
        
        if stdin:
            process = subprocess.Popen(commands, stdin=subprocess.PIPE,
                stdout= subprocess.PIPE, stderr= subprocess.PIPE, shell=shell)
        else:
            process = subprocess.Popen(commands, 
                stdout= subprocess.PIPE, stderr= subprocess.PIPE, shell=shell)
            
        stdout_thread = threading.Thread(target=output_reader, args=(process,))
        stdout_thread.start()
        
        stderr_thread = threading.Thread(target=stderr_reader, args=(process,))
        stderr_thread.start()
        
        sys.stdout.copy_to_thread(stdout_thread.ident)
        sys.stderr.copy_to_thread(stderr_thread.ident)
        
        while True:
           cmd = input('')
           if cmd == '': break
           process.stdin.write(cmd.encode() + '\n'.encode())
           process.stdin.flush()      

        process.stdin.close()        
        process.terminate()
        
    def pty(self, command='cmd', cwd=None, textmode='ansi', width=80):
        """
        Setup a virtual terminal.
        Stdout of the executing process live printed.
        textmode = 'ansi' or 'raw'
        """
        from winpty import PtyProcess
        #install pywinpty
        
        #The orginal terminal is killed or hidden?
        #logging.root.handlers[0] becomes invalid?    
        if isinstance(logging.root.handlers[0], logging.StreamHandler):
            logging.root.handlers.pop(0)
            
        #WINPTY_SHOW_CONSOLE to 1
        os.environ['WINPTY_SHOW_CONSOLE'] = '1'        
            
        #proc = PtyProcess.spawn(command, cwd=cwd)
        proc = PtyProcess.spawn(command, dimensions=(24, width))
        
        # def output_reader(proc):
            #PTYESC = '\033]'
            #while proc.isalive():        
                # text = proc.readline()
                # if text == '': raise EOFError('End of File')
                # sys.stdout._write_mode(text, textmode)
                
        def output_reader(proc):
            """Read one line from the pseudoterminal as bytes.

            Can block if there is nothing to read. Raises :exc:`EOFError` if the
            terminal was closed.
            """
            buf = []
            while True:
                try:
                    ch = proc.read(1)
                except EOFError:
                    sys.stdout._write_mode(''.join(buf)+'\n', textmode)
                    sys.stdout._write_mode('End of Process\n', textmode)
                    return
                buf.append(ch)
                if ch == '\n':
                    sys.stdout._write_mode(''.join(buf), textmode)
                    buf.clear()
        
        stdout_thread = threading.Thread(target=output_reader, args=(proc,))
        stdout_thread.start()
        sys.stdout.copy_to_thread(stdout_thread.ident)

        while proc.isalive():
            try:
                cmd = input('', timeout=1)
                proc.write(cmd + '\r\n')
            except queue.Empty:
                pass
                
        
    def pprint(self, var):
        """
        Do a `pretty print <https://docs.python.org/3.8/library/pprint.html>`_ of var.
        The user can also use `var!!` to call this function.               
        """
        pprint.pprint(var)
        
        
    def magic(self, cmd):
        """
        Magic commands like in IPython.
        """
        cmd, *args = shlex.split(cmd)
        if cmd == 'cd':
            os.chdir(args[0])            
            
        elif cmd == 'pwd':
            print(Path('.').resolve())
            
        elif cmd in ['ls', 'dir']:
            self.popen('dir')
            
        elif cmd == 'tb':
            traceback.print_last()
            
        elif cmd == 'info':
            self.info()
            
        elif cmd == 'who':            
            tbl = RecordTable(['name', 'repr', 'str'])
            
            for key in list(self.wsdict.keys()):
                if key.startswith('_'): continue
                obj = self.wsdict[key]
                tbl.add_row((key, repr(obj), str(obj)))
                
            print(tbl)            
            
            
    def tree(self, dir_path: Path, level: int=-1, limit_to_directories: bool=False,
             length_limit: int=1000):
        """Given a directory Path object print a visual tree structure"""
        space =  '    '
        branch = '│   '
        tee =    '├── '
        last =   '└── '

        dir_path = Path(dir_path) # accept string coerceable to Path
        files = 0
        directories = 0
        
        def inner(dir_path: Path, prefix: str='', level=-1):
            nonlocal files, directories
            if not level: 
                return # 0, stop iterating
            if limit_to_directories:
                contents = [d for d in dir_path.iterdir() if d.is_dir()]
            else: 
                contents = list(dir_path.iterdir())
            pointers = [tee] * (len(contents) - 1) + [last]
            for pointer, path in zip(pointers, contents):
                if path.is_dir():
                    yield prefix + pointer + path.name
                    directories += 1
                    extension = branch if pointer == tee else space 
                    yield from inner(path, prefix=prefix+extension, level=level-1)
                elif not limit_to_directories:
                    yield prefix + pointer + path.name
                    files += 1
                    
        print(dir_path.name)
        iterator = inner(dir_path, level=level)
        for line in islice(iterator, length_limit):
            print(line)
        if next(iterator, None):
            print(f'... length_limit, {length_limit}, reached, counted:')
        print(f'\n{directories} directories' + (f', {files} files' if files else ''))
                
        
    def start_in_this_thread(self, cqs, console_id=None):      
        QueueInterpreter.create_and_interact(self, cqs, None, console_id)              
        
        
    @staticmethod
    def get_completer_data(text, max=1000, wild=False, wsmode=None):        
        
        shell = Shell.instance        
            
        if wsmode == 'input':
            workspace = shell.input_frame.f_locals
            
            if COMPLETER == 'native':
                comp = Completer(workspace)
                
            else:
                comp = LiveCompleter(workspace, multikey=MULTIKEY)
                
        else:
            comp = shell.comp
        
        items = []
        for state in range(max):
            if comp.complete.__func__.__code__.co_argcount == 3:
                # The Python Original rlcompleter.
                item = comp.complete(text, state)
            else:
                # Needs an extra argument: 'wild'.
                item = comp.complete(text, state, wild)
            if item is None:
                # Reached the end (no more attributes).
                break
            #print(item)
            items.append(item)
        return items        

        
    def input(self, message='', timeout=None):
        ident = threading.get_ident()

        frame = sys._getframe(1)
        self.input_frame = frame
        
        if ident in self.interpreters.keys():
            if gui.is_main():
                return gui.inputdlg(message)
            else:
                prior_console_mode = gui.console.set_mode('input')
                print(message, end='')
                mode, args, callback = self.stdin.read(timeout=timeout)
                gui.console.set_mode(prior_console_mode)
                return args[0]
        else:
            return self.__input__(message)

            
    def execfile(self, filepath, globals=None, locals=None):
        """
        Execute a Python file
        """
        filepath = str(Path(filepath).absolute())
        source = open(filepath, 'r').read()
        code = compile(source, filepath, 'exec')
        locals = locals or {}
        locals["__file__"] = filepath
        exec(code, globals, locals)
        
    def execfilews(self, filepath, wsname='__execfilews__'):
        """
        Execute a Python file in a new workspace.
        Place the workspace in shell
        """    
        filepath = str(Path(filepath).absolute())
        ws = dict()
        ws['__file__'] = filepath
        self.execfile(filepath, ws)
        self.wsdict[wsname] = ws
        return ws
    
    @staticmethod    
    def set_logger_level(level=20):        
        root = logging.getLogger()
        root.setLevel(level)
        
        for handler in root.handlers:
            handler.setLevel(level)
        
    @staticmethod
    def get_sys_paths(customs_only=True):
        """
        List the sys.paths.
        
        :param bool customs_only: List only paths not part of the python.exe directory.
        """
        base = Path(sys.executable).parent
        custom_paths = []
        for path in sys.path:
            path = Path(path)
            if customs_only:
                if base in path.parents:
                    continue
                elif base == path:      
                    continue  
                elif path == Path('.'):
                    continue                
            custom_paths.append(str(path))
        return custom_paths
        
    @staticmethod
    def set_sys_paths(new_sys_paths):
        """
        Set new content for sys.path.
        """
        sys.path.clear()
        sys.path.extend(new_sys_paths)
        print(f'The new paths are {sys.path}')
        
    @staticmethod
    def add_sys_paths(sys_paths):
        for path in sys_paths:
            if not path in sys.path:
                sys.path.append(path)
        
    @staticmethod
    def get_live_paths():
        #from ..live import manager
        return manager.path.copy()
        
    @staticmethod
    def set_live_paths(new_live_paths):
        #from ..live import manager     
        manager.path.clear()
        manager.path.extend(new_live_paths)
        print(f'The new live paths are {manager.path}')
        
    @staticmethod
    def reload_scripts():
        manager.update_now(True)
        
        
    def who(self, varname=None):
        value = self.wsdict.get(varname)        
        print(f'{varname}: {type(value)} = ')
        self.pprint(value)
        
    
