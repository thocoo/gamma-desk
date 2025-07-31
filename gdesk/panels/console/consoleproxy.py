import sys
import threading
import multiprocessing
import traceback

from ...core.gui_proxy import GuiProxyBase, StaticGuiCall, gui
from ...core.shellmod import Shell


class ProcessError(BaseException):
    # With as message the formatted traceback
    # of the error caused in the other process
    pass


class MpTask(object):
    
    
    def __init__(self, console_id):
        self.lock = multiprocessing.Lock()
        self.console_id = console_id
        self.done = False
        self.result = None
        self.ex = None
        self.tb_message = None
        

    def _accept_error(self, mode, error_code, result):      
        
        if error_code == 5:
            self.ex, self.tb_message = result
            
        self.lock.release()
        
        
    def _accept_result(self, result):
        self.result = result
        self.lock.release()
        
        
    def join(self):
        if self.done: return self.result
        
        self.lock.acquire()
        self.done = True                
        
        # TO DO
        # There is a risk that print messages are not yet processed
        # Closing before this will cause 
        #    RuntimeError: Internal C++ object (StdPlainOutputPanel) already deleted.
        gui.console.close(self.console_id)
        
        if not self.ex is None:
            raise ProcessError(self.tb_message)
                   
        return self.result
        
       
class ConsoleGuiProxy(GuiProxyBase):    
    category = 'console'
    opens_with = ['.py']
    
    def __init__(self):
        pass

        
    def attach(self, gui):
        gui.console = self
        gui.clc = self.clc
        return 'console'

        
    @StaticGuiCall 
    def open(filepath):
        panel = gui.qapp.panels.selected('console')
        ConsoleGuiProxy._gui_execute_file(filepath, panel.panid)


    @StaticGuiCall
    def console(pandid=None, consoletype='thread'):
        """
        
        :param str consoletype: 'main', 'thread', 'child', 'child-thread', 'process'
        """        
        if pandid is None:
            panel = gui.qapp.panels.selected('console')
        else:
            panel = gui.qapp.panels.select_or_new('console', pandid, consoletype)                
            
        return panel.panid    

        
    @StaticGuiCall
    def clc():
        """Clear the Console Output"""      
        # For now, jus take the active console
        # Note that this is not always correct
        # Should first search for the console of the current process and thread
        sys.stdout.flush()
        sys.stderr.flush()
        panel = gui.qapp.panels.selected('console')
        panel.stdio.stdOutputPanel.clear()
        

    @StaticGuiCall
    def text():
        panel = gui.qapp.panels.selected('console')
        text = panel.stdio.stdOutputPanel.toPlainText()
        return text


    def set_mode(self, mode='input', panid=None):
        if panid is None:
            shell = Shell.instance
            ident = threading.get_ident()
            panid = shell.interpreters[ident].console_id            
        return ConsoleGuiProxy._gui_set_console_mode(mode, panid)


    def show_me(self):
        shell = Shell.instance
        this_panid = shell.this_interpreter().console_id  
        self.show(this_panid)

    
    @StaticGuiCall    
    def show(panid):
        console = gui.qapp.panels['console'][panid]
        console.show_me()


    @StaticGuiCall       
    def _gui_set_console_mode(mode='input', panid=None):
        console = gui.qapp.panels['console'][panid]  
        old_mode = console.stdio.stdInputPanel.mode      
        console.set_mode(mode) 
        return old_mode


    @StaticGuiCall       
    def release_side_thread(panid):
        task = gui.qapp.panels['console'][panid].task
        task.release_control()


    @staticmethod
    def execute(code_str):
        shell = Shell.instance
        exec(code_str, shell.wsdict)


    def execute_code(self, code_string, panid=None):
        shell = Shell.instance
        this_panid = shell.this_interpreter().console_id        
        if panid is None or this_panid == panid:
            exec(code_string, shell.wsdict)
        else:
            ConsoleGuiProxy._gui_execute_code(code_string, panid)            


    @StaticGuiCall
    def _gui_execute_code(code_string=None, panid=None):
        """
        Execute code in ANOTHER console        
        """
        console = gui.qapp.panels.select_or_new('console', panid)
        console.stdio.stdInputPanel.execute_commands(code_string)        


    def execute_file(self, filepath, panid=None):
        shell = Shell.instance
        this_panid = shell.this_interpreter().console_id        
        if panid is None or this_panid == panid:
            shell.execfile(filepath, shell.wsdict)
        else:
            ConsoleGuiProxy._gui_execute_file(filepath)


    @StaticGuiCall
    def _gui_execute_file(filepath, panid=None):
        """
        Execute a file in ANOTHER console
        """
        console = gui.qapp.panels.select_or_new('console', panid)
        callback = console.stdio.stdInputPanel.retval_ready
        console.task.send_command(f"_ = shell.execfilews(r'{filepath}')", callback)
        
        
    @StaticGuiCall        
    def sync_paths(source_panid=0, target_panid=1):
        """
        Syncing sys.path and the live paths from source to target.
        """
        from ...core.shellmod import Shell
        
        source_task = gui.qapp.panels['console'][source_panid].task
        target_task = gui.qapp.panels['console'][target_panid].task
        
        sys_paths = source_task.call_func(Shell.get_sys_paths, wait=True)  
        target_task.call_func(Shell.add_sys_paths, args=(sys_paths,))
        
        live_paths = source_task.call_func(Shell.get_live_paths, wait=True)
        target_task.call_func(Shell.set_live_paths, args=(live_paths,))

    
    @StaticGuiCall    
    def child(init_caller, *args):
        panel = gui.qapp.panels.select_or_new('console', None, 'child')
        #panel.window().toggleStatOnTop(True)
        panel.task.wait_process_ready()        
                    
        panel.task.call_func(init_caller, args=args, callback=None)           
        return panel.panid
        
    
    @StaticGuiCall    
    def child_live_exec(live_func, *args, **kwargs):
        shell = Shell.instance
        this_panid = shell.this_interpreter().console_id        
        new_panel = gui.qapp.panels.select_or_new('console', None, 'child')
        new_panel.task.wait_process_ready()        
        ConsoleGuiProxy.sync_paths(this_panid, new_panel.panid)   
        
        mptask = MpTask(new_panel.panid)  
        mptask.lock.acquire()        
            
        new_panel.task.call_func_ext(ConsoleGuiProxy.use_exec, args=(live_func.__module__, live_func.__name__) + args, kwargs=kwargs,
            callback=mptask._accept_result, callerr=mptask._accept_error)
            
        return mptask
        
        
    @staticmethod    
    def use_exec(live_module, func_name, *args, **kwargs):
        from gdesk import use
        return getattr(use(live_module), func_name)(*args, **kwargs)
        