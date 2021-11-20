import sys, io, os, builtins
import json
import signal
import traceback
import threading
import multiprocessing
import textwrap
import types
import pathlib
import time
import pickle
import configparser
import time
import collections
import platform
import logging
from multiprocessing import Process, Lock
from queue import Queue
    
try:
    import zmq
    zmq_context = zmq.Context()
    
except:
    pass    


logger = logging.getLogger(__name__)   

#In case of Process call, this module will be important by the child 
#process by the unpickling of the CommQueues
from .conf import config, configure
from .. import refer_shell_instance

#Configure in case of the child process before importing anthing else of ghawk2
configure(matplotlib={'backend':'svg'})
process_name = multiprocessing.current_process().name
logger.debug(f'import of {__name__} by {process_name}\n')

from .shellmod import Shell
from .gui_proxy import GuiProxy
from .interpreter import Interpreter, QueueInterpreter
from .comm import NonDuplexQueue, ZmqQueues, CommQueues

PROCESSES = collections.OrderedDict()

here = pathlib.Path(__file__).parent  

        
class TimeOutGuiCall(object):
    def __init__(self, gui_proxy, timeout, callback, args=()):
        self.gui_proxy = gui_proxy
        self.callback = callback
        self.called = False
        self.timeout = timeout
        self.thread = threading.Thread(target=self.delay_call, args=args)
        self.thread.start()
        self.lock = threading.Lock()
        
    def delay_call(self, *args):
        time.sleep(self.timeout)
        if self.called: return
        try:
            self.lock.acquire()
            self.called = True
            self.gui_proxy._call(self.callback, *args)
        finally:
            self.lock.release()
        
    def call(self, *args):
        if self.called: return
        try:
            self.lock.acquire()
            self.called = True
            self.callback(*args)
        finally:
            self.lock.release()
        

class TaskBase(object):   
    def __init__(self, tasktype='process'):
        self.tasktype = tasktype
        self.process_id = -1
        self.thread_name = 'invalid'
        self.thread_id = -1
        self.panid = None
        
    @property
    def stdin_queue(self):
        return self.cqs.stdin_queue        
    
    @property
    def stdout_queue(self):
        return self.cqs.stdout_queue
        
    @property
    def flow_queue(self):
        return self.cqs.flow_queue     

    @property
    def return_queue(self):
        return self.cqs.return_queue      

    def is_current_thread(self):
        return self.process_id == os.getpid() and self.thread_id == threading.get_ident()          

    def getReturnedValues(self, mode, error_code, result):
        if error_code == 0:
            pass
        else:
            print(f'WARNING with error code {error_code}\n{mode} {result}')
            
        return mode, error_code, result

    def send_command(self, command, callback=None):
        return self.send_func_and_call('interprete', (command,), callback)
        
    def send_input(self, text):
        return self.send_func_and_call('input', (text,))
        
    def evaluate(self, *args, multiple=False):
        if multiple:
            return self.send_func_and_call('eval', args, wait=True)
        else:
            result = self.send_func_and_call('eval', args, wait=True)
            return result[0]
        
    def call_func(self, func, args=(), callback=None, wait=False, queue='stdin'):           
        if not isinstance(func, str):
            func = self.gui_proxy.encode_func(func)
        
        if queue == 'stdin':
            return self.send_func_and_call('func', (func, args), callback, wait)
        elif queue == 'flow':
            return self.send_func_and_call('flow_func', (func, args), callback, wait)
            
    def send_func_and_call(self, mode, args=(), callback=None, wait=False, timeout=0):
        if callback is None and not wait:
            callback = self.getReturnedValues    
    
        if not callback is None:
            if timeout == 0:
                call_back_id = self.gui_proxy.encode_func(callback, register=True)  
                
            else:
                callbackwrap = TimeOutGuiCall(self.gui_proxy, timeout, callback, args=('timeout', 5, None))                
                call_back_id = self.gui_proxy.encode_func(callbackwrap.call, register=True)
        else:
            call_back_id = None
            
        if mode in ['input', 'interprete', 'func', 'console id', 'exit']:
            self.stdin_queue.put((mode, args, call_back_id))
            
            if self.is_current_thread():
                self.mainshell.interpreters[self.thread_id].execute()
            
        elif mode in ['flow', 'eval', 'flow_func']:        
            self.flow_queue.put((mode, args, call_back_id))
            
            if self.is_current_thread():
                self.mainshell.interpreters[self.thread_id].control()        

        if callback is None and wait:
            #This is an high risk for a deathlock
            #Waiting here will block the eventloop
            #If still prior callbacks are queued, the eventloop can not respond to it -> deathlock     
            
            mode, error_code, result = self.return_queue.get(timeout=5)               
                
            assert error_code == 0
            return result               
        
    def register(self, mainshell):
        #mainshell.tasks[(self.process_id, self.thread_id)] = self
        pass
        
    def print_trace(self):
        self.send_func_and_call("flow", ("trace",))        
        
    def print_locals(self):
        self.send_func_and_call("flow", ("locals",))                
        
    def sync_break(self):
        self.send_func_and_call("flow", ("sync_break",))
        
    def async_break(self):
        self.send_func_and_call("flow", ("KeyboardInterrupt",))  
        
    def system_exit(self):
        self.send_func_and_call("flow", ("system_exit",))          
        
    def kill(self):
        import psutil
        
        parent = psutil.Process(self.process_id)
        for child in parent.children(recursive=True):
            child.kill()
            
        parent.kill()
        
        tasks = list(PROCESSES[self.process_id].values())
        for task in tasks:
            task.console.close_panel()     
            
    def flow(self, *args):
        self.send_func_and_call("flow", args)
        
    def flow_alive(self, callback, timeout=5):        
        self.send_func_and_call("flow", ("heartbeat",), callback, timeout=timeout)        
        
    def set_tracing(self, enable=True):
        self.send_func_and_call("flow", ("set_tracing", enable))
        
    def set_timeit(self, enable=True):
        self.send_func_and_call("flow", ("set_timeit", enable))
        
    def enable_profiling(self):
        self.send_func_and_call("flow", ("enable_profiling",))        
        
    def process_ready(self, *args):
        #Gui will freeze until something comes back from the return_queue
        anstype, error_code, (pid, tname, tid) = args
        
        self.process_id = pid
        self.thread_name = tname
        self.thread_id = tid
        
        if not self.process_id in PROCESSES:
            PROCESSES[self.process_id] = dict()
            
        PROCESSES[self.process_id][self.thread_id] = self
        
        #This can maybe come to soon, before the console was created
        if hasattr(self, 'console'):
            self.console.refresh_pid_tid()
            # Panel id is communicated on creation
            # self.send_func_and_call("console id", (self.console.panid,))
            
    def unregister(self):
        PROCESSES[self.process_id].pop(self.thread_id)
        if len(PROCESSES[self.process_id]) == 0:
            PROCESSES.pop(self.process_id)

    def set_flusher(self, func):
        self.gui_proxy.set_func_hook(-1, func)  
        
    def wait_process_ready(self, timeout=3):
        from qtpy import QtWidgets
        
        qapp = QtWidgets.QApplication.instance()
        for i in range(timeout * 10):
            qapp.processEvents()
            if self.thread_name != 'invalid': break
            time.sleep(0.1)


class ThreadTask(TaskBase):  
    flow_queues = dict()    
    
    def __init__(self, mainshell, new_thread=True):    
        self.new_thread = new_thread         
        
        if new_thread:
            super().__init__('thread')    
        else:
            super().__init__('main')    

        self.mainshell = mainshell        

        self.cqs = CommQueues(Queue)

        self.gui_proxy = GuiProxy(mainshell._qapp,
            self.cqs.gui_call_queue,   #None
            self.cqs.gui_return_queue, #None
            self.process_ready)

    def start(self):
        if self.new_thread:                              
            self.mainshell.new_interactive_thread(self.cqs, self.gui_proxy, console_id=self.panid)

        else:
            self.gui_proxy.block = False
            
            self.thread = threading.currentThread()   
            self.command_loop(self.cqs, self.gui_proxy, self.panid)        

    def finish(self, close=False):
        if self.thread_name == 'MainThread':
            print("You can't finish the meain thread")
            return
            
        super().finish(close)        
        
    def command_loop(self, cqs, gui_proxy=None, console_id=None):        

        thread_id = threading.get_ident()
        ThreadTask.flow_queues[thread_id] = cqs.flow_queue
        
        QueueInterpreter(self.mainshell, cqs, gui_proxy, console_id)


class ProcessTask(TaskBase):
    def __init__(self, mainshell, cqs=None):
        super().__init__('child')
        
        if cqs is None:
            self.cqs = CommQueues(multiprocessing.Queue, process=True)
            self.start_child = True
        else:
            self.cqs = cqs            
            self.start_child = False            
        
        self.gui_proxy = GuiProxy(mainshell._qapp,
            self.cqs.gui_call_queue,
            self.cqs.gui_return_queue,
            self.process_ready)        
        
    def start(self):
        #no existing queue from an existing master process
        #Start a new child process
        if self.start_child:
            self.process = Process(target=ProcessTask.start_child_process, args=(self.cqs, self.panid), daemon=True)
            self.process.start()                   
        
        self.flusher = None
                
    @staticmethod    
    def start_child_process(cqs, panid=None):            
        try:
            shell = Shell()
            refer_shell_instance(shell)
            shell.start_in_this_thread(cqs, panid)
            
        finally:
            import psutil
            sys.__stdout__.write(f'End of start_child_processs\n')
            sys.__stdout__.flush()
            proc = psutil.Process()
            proc.kill()

class ProcessThreadTask(TaskBase):
    def __init__(self, mainshell, master_process_task, queue_type='pipe'):
        super().__init__('child-thread')
        self.master_process_task = master_process_task
        
        if queue_type == 'pipe':
            self.cqs = CommQueues(NonDuplexQueue, process=True)          
            
        elif queue_type == 'zmq':
            self.cqs = ZmqQueues()
            self.cqs.setup_as_server()
            
        self.gui_proxy = GuiProxy(mainshell._qapp, self.cqs.gui_call_queue, self.cqs.gui_return_queue, self.process_ready)
          
    def start(self):          
        #Problems if master_process_task didn't not yet finished prior command
        #For example master_process_task is still queues flushes of a big print loop
        #The master_process_task.return_queue still contains the prior return result
        self.master_process_task.call_func(Shell.new_interactive_thread, args=(self.cqs, None, True, self.panid), queue='flow')
        
