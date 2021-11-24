import sys
import io
import os
import traceback
import queue
import ctypes
import time
import threading
import multiprocessing
import builtins
import psutil
import logging
import inspect
import cProfile
import pstats
from queue import Queue
from codeop import CommandCompiler
from datetime import timedelta
from pathlib import Path

import psutil

from .conf import config
from . import stdinout
from .stdinout import ProcessStdInput
from .gui_proxy import GuiProxy, GuiMap, gui

logger = logging.getLogger(__file__)

class SyncBreaked(Exception):
    pass
    

class QueueInterpreter(object):
    def __init__(self, shell, cqs, gui_proxy=None, console_id=None):
    
        self.shell = shell
        self.cqs = cqs
        
        this_process = multiprocessing.current_process()
        this_thread = threading.currentThread()
        self.thread_id = thread_id = this_thread.ident
        self.console_id = console_id
        
        self.enable_trace = True
        self.breakable = False
        self.break_sent = False
        self.stop = False
        self.timeit = False
        self.enable_inspect = False
        
        self.enable_profile = False
        self.profile_sortby = 'cumulative'
        
        self.control_thread = None
        
        if gui_proxy is None:        
            self.gui_proxy = GuiProxy(None, cqs.gui_call_queue, cqs.gui_return_queue)
        else:
            self.gui_proxy = gui_proxy
        
        self.register_thread(thread_id, cqs)
        
        self.interpreter = Interpreter(self.shell.wsdict, thread_id)     
        self.shell.interpreters[self.thread_id] = self
        
        callbackargs = ('process', 0, (os.getpid(), this_thread.name, threading.get_ident()))        
        self.gui_proxy._call(-2, *callbackargs)
        
        print(f'{sys.executable}')
        print(f'Python {".".join(str(v) for v in sys.version_info)}')
        print(os.getcwd())
        print(f'{this_process.name} [{os.getpid()}] {this_thread.name} [{threading.get_ident()}]')
        
    def register_thread(self, tid, cqs):        
        self.stdout = stdinout.FlushPipeStream(cqs.stdout_queue, lambda: self.gui_proxy._call_no_wait(-1))
        self.shell.stdout.route_stream(self.stdout, tid)
        self.stderr = stdinout.ErrLogStream()
        self.shell.stderr.route_stream(self.stderr, tid)
        
        ProcessStdInput.stdin_queues[tid] = cqs.stdin_queue                            
        GuiMap.gui_proxies[tid] = self.gui_proxy    

    def unregister_thread(self):
        tid = self.thread_id
        self.shell.stdout.streams.pop(tid)
        self.shell.stderr.streams.pop(tid)    
        self.shell.interpreters.pop(tid)        
        ProcessStdInput.stdin_queues.pop(tid)
        GuiMap.gui_proxies.pop(tid)
    
    @staticmethod
    def create_and_interact(shell, cqs, gui_proxy=None, console_id=None):
        try:
            queuedinter = QueueInterpreter(shell, cqs, gui_proxy, console_id)
            queuedinter.interact()
            
        finally:
            sys.__stdout__.write(f'End of create_and_interact\n')
            sys.__stdout__.flush()        
        
    def interact(self):
        self.control_thread = threading.Thread(target=self.control_loop, name=f'control_thread{self.thread_id}', daemon=True)
        self.control_thread.start()   
        
        self.commandLoop()
        
    def control_loop(self):
        flowcode = 1
        
        self.shell.stdout.route_stream(self.stdout)
        
        try:
            while flowcode == 1:
                flowcode = self.control()
                
        finally:
            self.shell.stdout.unregister()
            sys.__stdout__.write(f'Exiting control loop of thread {self.thread_id}\n')
            sys.__stdout__.flush() 
        
    def commandLoop(self):
        flowcode = 1
        
        try:
            while flowcode == 1:
                flowcode = self.execute()   

        finally:
            self.unregister_thread()
            sys.__stdout__.write(f'Exiting command loop of thread {self.thread_id}\n')
            sys.__stdout__.flush()            
            
        
    def system_tracer(self, *args):
        if self.enable_trace and self.stop:
            raise SyncBreaked('Breaked by system tracer')
        return None
        
    def get_current_trace(self, back=50):
        lines = ''
        for frame in self.interpreter.get_code_frames(back):        
            fi = inspect.getframeinfo(frame)
            
            file_position = '  File "%s", line %d, in %s\n' % (fi.filename, fi.lineno, fi.function)
            file_code = ''
            try:
                for line in fi.code_context:
                    file_code += line
            except:
                pass
            lines = file_position + file_code + lines
        
        return lines        
        
    def get_current_locals(self, back=5):
        lines = ''
        
        for frame in self.interpreter.get_code_frames(back):
            for key, val in frame.f_locals.items():
                if key.startswith('_'):
                    continue
                lines += f'{key}: {val}\n'
                
        return lines    

    def set_console_mode(self, mode):
        #if not self.console_id is None:
        gui.console.set_mode(mode, self.console_id)        
        
    def control(self):
        cqs = self.cqs
        interpreter = self.interpreter
        gui_proxy = self.gui_proxy    
        
        while True:
            try:
                mode, args, callback = cqs.flow_queue.get()
                break
            
            except KeyboardInterrupt:
                pass          
                
        if mode == 'flow':
            cmd, *cargs = args
            
            if cmd == 'heartbeat':
                callbackargs = (mode, 0, 'heartbeat')
                retvalue = 1
            
            elif cmd == 'set_tracing':
                self.enable_trace = cargs[0]
                callbackargs = (mode, 0, f'Enable Trace: {self.enable_trace}')
                retvalue = 1
                
            elif cmd == 'set_timeit':
                self.timeit = cargs[0]
                callbackargs = (mode, 0, f'Enable Time It: {self.timeit}')
                retvalue = 1
                
            elif cmd == 'enable_profiling':
                self.enable_profile = True
                callbackargs = (mode, 0, f'Enable profiling')
                retvalue = 1
                
            elif cmd == 'toggle_inspect':
                self.enable_inspect = not self.enable_inspect
                callbackargs = (mode, 0, f'enable_inspect={self.enable_inspect}')
                retvalue = 1                
            
            elif cmd == 'trace':
                print(self.get_current_trace())
                callbackargs = (mode, 0, 'Trace printed')
                retvalue = 1
                
            elif cmd == 'locals':
                print(self.get_current_locals())
                callbackargs = (mode, 0, 'Locals printed')
                retvalue = 1

            elif cmd == 'sync_break':
                if not threading.currentThread().ident == self.thread_id and self.enable_trace:
                    self.stop = True
                    callbackargs = (mode, 0, 'Thread is asked to stop')
                else:
                    callbackargs = (mode, 1, 'Tracing is not enabled')
                retvalue = 1

            elif cmd == 'KeyboardInterrupt':
                if not threading.currentThread().ident == self.thread_id and self.breakable:
                    self.break_sent = True
                    self.interpreter.async_break()                    
                    callbackargs = (mode, 0, 'KeyboardInterrupt send')
                else:
                    callbackargs = (mode, 1, 'KeyboardInterrupt not send')
                retvalue = 1

            elif cmd == 'system_exit':
                self.interpreter.async_system_exit()
                callbackargs = (mode, 0, 'SystemExit send')
                retvalue = 0
                
            elif cmd == 'kill':                
                parent = psutil.Process(os.getpid())
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()                
            
            elif cmd == 'finish':
                callbackargs = (mode, 0, 'Finishing')
                retvalue = 0

            else:
                callbackargs = (mode, 1, 'Command unkown')
                retvalue = 1                              
                
        elif mode == 'flow_func':
            func = args[0]
            args = args[1]
            if isinstance(func, str):   
                print('str is not supported as function pointer')  
                callbackargs = (mode, 1, 'str is not supported as function pointer')
                retvalue = 1

            elif isinstance(func, tuple):            
                try:                    
                    func = gui_proxy.decode_func(func)
                    result = func(*args)
                    error_code = 0
                    
                except Exception:
                    traceback.print_exc() 
                    result = None
                    error_code = 1
                    
                callbackargs = (mode, error_code, result)
                retvalue = 1                   
            
        elif mode == 'eval':
            try:                    
                result = [eval(arg, self.shell.wsdict) for arg in args]
                error_code = 0
                
            except Exception:
                traceback.print_exc()
                result = None
                error_code = 1
                
            callbackargs = (mode, error_code, result)
            retvalue = 1            
                
        else:        
            callbackargs = (mode, 1, 'unkown')
            retvalue = 1
            
        if callback is None:
            #There always should be a callback: {callbackargs}')
            #This is only used for the evaluate
            cqs.return_queue.put(callbackargs)
        else:
            gui_proxy._call(callback, *callbackargs)                                                                                    

        return retvalue          
        
    def execute(self):    
        cqs = self.cqs
        interpreter = self.interpreter
        gui_proxy = self.gui_proxy    
        
        while True:
            try:
                content = cqs.stdin_queue.get(timeout=3)
                mode, args, callback = content
                break
            
            except queue.Empty:
                pass
            
            except KeyboardInterrupt:
                pass

        if mode in ['interprete', 'func']:
            error_code = None
            result = None
            
            try:
                self.breakable = True
                self.stop = False
                
                #the tracer seemed to be disabled after every sync break ???
                if self.enable_trace:
                    sys.settrace(self.system_tracer)
                else:
                    sys.settrace(None)
                    
                if self.enable_profile:
                    self.profile = cProfile.Profile()
                    self.profile.enable()
                
                start_moment = end_moment = time.perf_counter()
                redbull_timeout = config['console']['redbull']
                if redbull_timeout > 0:
                    self.gui_proxy.redbull.enable(redbull_timeout)
                    
                self.set_console_mode('running')
                
                if mode == 'func':
                    func = gui_proxy.decode_func(args[0])
                    func_args = args[1]
                    
                    if self.enable_inspect:                    
                        try:
                            filename = inspect.getfile(func)
                            print(filename)
                        except:
                            print('filename not found')
                            
                        try:
                            source = inspect.getsource(func)
                            print(source)
                        except:
                            print('source not found')
                            
                    error_code, result = interpreter.use_one_func(func, func_args)
                    self.set_console_mode('interprete')
                else:
                    error_code, result = interpreter.use_one_command(*args)
                
                if self.enable_profile:
                    self.profile.disable()
                    self.enable_profile = False                    
                    profile_stats = pstats.Stats(self.profile).sort_stats(self.profile_sortby)
                    profile_stats.print_stats()

                sys.settrace(None)                
                
                if self.break_sent:
                    #A async KeyboardInterrupt was sent but still have to occur
                    #This situation is rare, but can happen
                    #Keep on stepping in the Python interpreter
                    print('WARNING: KeyboardInterrupt is on its way')
                    for i in range(100):
                        time.sleep(0.010)                                   
                
            except KeyboardInterrupt:                        
                error_code = 3
                result = 'Thread Interrupted by KeyboardInterrupt'
                print(result)                
                
            except SyncBreaked:
                error_code = 3
                result = 'Thread Interrupted by SyncBreaked'
                print(result)
                
            except Exception as ex:
                error_code = 4
                result = repr(ex)                
                
            finally:
                #Finish the side thread
                self.breakable = False
                self.break_sent = False                    
                self.gui_proxy.redbull.disable()
                
                if self.timeit:
                    end_moment =  time.perf_counter()                 
                    print(f'Elapased time {end_moment-start_moment} s')                                
                    
                callbackargs = (mode, error_code, result)
                retvalue = 1                
            
        elif mode == 'exit':
            self.unregister_thread()
            callbackargs = (mode, 0, 'Exiting')
            retvalue = 0                             

        else:        
            callbackargs = (mode, 1, 'unkown')
            retvalue = 1
            
        if callback is None:
            #There always should be a callback: {callbackargs}')
            #This is only used for the evaluate
            cqs.return_queue.put(callbackargs)
        else:
            gui_proxy._call(callback, *callbackargs)                                                                                    

        return retvalue  
        

class Interpreter(object):
    def __init__(self, workspace=None, thread_id=None):
        if workspace is None:
            workspace = dict()
            
        self.workspace = workspace
        self.compile = CommandCompiler()  
        self.thread_id = thread_id
        
    def compile_source(self, source, filename="<input>", symbol="auto"):
        """
        Compile and run some source in the interpreter.

        Arguments are as for compile_command().

        One several things can happen:

        1) The input is incorrect; compile_command() raised an
        exception (SyntaxError or OverflowError).  A syntax traceback
        will be printed by calling the showsyntaxerror() method.

        2) The input is incomplete, and more input is required;
        compile_command() returned None.  Nothing happens.

        3) The input is complete; compile_command() returned a code
        object.  The code is executed by calling self.runcode() (which
        also handles run-time exceptions, except for SystemExit).

        The return value is True in case 2, False in the other cases (unless
        an exception is raised).  The return value can be used to
        decide whether to use sys.ps1 or sys.ps2 to prompt the next
        line.
        """    
        if symbol == 'auto':
            if source.count('\n') == 0:  
                symbol = 'single'
            else:
                symbol = 'exec'

        #Compile the code, show syntax error
        try:
            code = self.compile(source, filename, symbol)
        except (OverflowError, SyntaxError, ValueError):
            # Case 1
            self.showsyntaxerror(filename)
            return 1, None
            
        if code is None:
            # Case 2
            # more code expected, nothing to do
            return 2, None                  

        return 0, code              

    def eval_expression(self, expression):
        """
        Execute a code object.

        When an exception occurs, self.showtraceback() is called to
        display a traceback.  All exceptions are caught except
        SystemExit, which is reraised.

        A note about KeyboardInterrupt: this exception may occur
        elsewhere in this code, and may not always be caught.  The
        caller should be prepared to deal with it.
        """
        try:
            return eval(expression, self.workspace)
        except (SystemExit, KeyboardInterrupt):            
            raise
        except:           
            self.showtraceback()              
            
    def showsyntaxerror(self, filename=None):
        """
        Display the syntax error that just occurred.

        This doesn't display a stack trace because there isn't one.

        If a filename is given, it is stuffed in the exception instead
        of what was there before (because Python's parser always uses
        "<string>" when reading from a string).

        The output is written by self.write(), below.
        """
        type, value, tb = sys.exc_info()
        sys.last_type = type
        sys.last_value = value
        sys.last_traceback = tb
        if filename and type is SyntaxError:
            # Work hard to stuff the correct filename in the exception
            try:
                msg, (dummy_filename, lineno, offset, line) = value.args
            except ValueError:
                # Not the format we expect; leave it alone
                pass
            else:
                # Stuff in the right filename
                value = SyntaxError(msg, (filename, lineno, offset, line))
                sys.last_value = value
        
        lines = traceback.format_exception_only(type, value)
        self.write_error(''.join(lines))
        
    def showtraceback(self):
        """
        Display the exception that just occurred.

        We remove the first stack item because it is our own code.

        The output is written by self.write(), below.
        """
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

        self.write_error(''.join(lines)) 

    def write_error(self, text):
        sys.stderr.write(text)
        
    def use_one_func(self, func, args):
        return 0, self.exec_func(func, args)
        
    def exec_func(self, func, args):
        try:
            return func(*args)
        except (SystemExit, KeyboardInterrupt, SyncBreaked):            
            raise
        except:           
            self.showtraceback() 
            
    def use_one_command(self, cmd):                        
        error_code, code = self.compile_source(cmd, symbol='auto')
        
        if error_code != 0:  
            return error_code, cmd
            
        else:
            return error_code, self.exec_code(code)
            
    def exec_code(self, code):
        """
        Execute a code object.

        When an exception occurs, self.showtraceback() is called to
        display a traceback.  All exceptions are caught except
        SystemExit, which is reraised.

        A note about KeyboardInterrupt: this exception may occur
        elsewhere in this code, and may not always be caught.  The
        caller should be prepared to deal with it.
        """
        try:
            return exec(code, self.workspace)
        except (SystemExit, KeyboardInterrupt, SyncBreaked):            
            raise
        except:           
            self.showtraceback()             
            
    def async_break(self):
        async_break(self.thread_id)  

    def async_system_exit(self):
        async_system_exit(self.thread_id) 
        
    def get_code_frames(self, back):
        frame = sys._current_frames()[self.thread_id]
        yield frame
        for _ in range(back):
            if frame.f_back is None:
                return
            frame = frame.f_back
            yield frame         

def async_raise(thread_id, exctype):
        """
        Raise the exception to the thread tid, performs cleanup if needed.
        """
        #the async exception is not immediate; it is checked every 100
        #bytecodes (=sys.getcheckinterval()).
        # if not inspect.isclass(exctype):
            # exctype = type(exctype)
        
        res = ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), ctypes.py_object(exctype))
        
        #receiver can clear errob y ctypes.pythonapi.PyErr_Clear()?
        if res == 0:
            raise ValueError("invalid thread id")
            
        elif res != 1:
            # """if it returns a number greater than one, you're in trouble,
            # and you should call it again with exc=NULL to revert the effect"""
            ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, None)
            raise SystemError("PyThreadState_SetAsyncExc failed")
            
        else:
            pass
            #print(f'{exctype} sent to thread id {thread_id}')

def async_break(thread_id):
    async_raise(thread_id, KeyboardInterrupt)
    
def async_system_exit(thread_id):
    async_raise(thread_id, SystemExit)    
