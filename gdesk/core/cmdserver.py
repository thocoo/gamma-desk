import queue
import io
import sys
import threading
import zmq

from gdesk import shell, gui


class StdOutStream(io.TextIOBase):
    
    def __init__(self, streamqueue):
        self.streamqueue = streamqueue


    def write(self, text):
        self._write_mode(text, 'ansi')                    
        

    def _write_mode(self, text, mode, prefix='', suffix=''):            
        if mode == 'ansi':
            text_fmt = f'{prefix}{text}{suffix}'
            
        self.streamqueue.put((mode, text_fmt))
        
            
    def flush(self): 
        pass


def serve(cqs):
    global loop
    
    loop = True
    
    tid = threading.get_ident()  
    
    sys.stdout.streams[tid].echo = StdOutStream(cqs.stdout_queue)
    sys.stdout.streams[tid].echo_enabled = True
    
    loop = True
    
    while loop:
        loop = one_command(cqs)
        
    gui.console.close()
    
        
def one_command(cqs):
    
    while True:
        
        try:
            content = cqs.stdin_queue.get(timeout=3)
            mode, args, callback = content
            break
        
        except queue.Empty:
            pass
        
        except KeyboardInterrupt:
            return False
            
        try:
            cqs.gui_call_queue.put(137)
            answer = cqs.gui_return_queue.get(timeout=3)
            
        except zmq.error.Again:
            return False
        
        except queue.Empty:
            return False                     
    
    if mode in ['interprete', 'func', 'func_ext']:
        error_code = None
        result = None
        
        try:      
            source = args[0]
            if source.count('\n') == 0:  
                symbol = 'single'
            else:
                symbol = 'exec'                
                
            code = compile(source, "<input>", symbol)
            result = exec(code, shell.wsdict)
            
        except KeyboardInterrupt:
            return
                
        except BaseException as ex:
            print(ex)
            
        finally:
            callbackargs = (mode, error_code, result)                                
    
    cqs.return_queue.put(callbackargs)
    return True

    