import io
import sys
import threading
import time
import logging
from logging.handlers import RotatingFileHandler
from logging import StreamHandler, Handler
from queue import Queue

from .conf import config
from .gui_proxy import gui

sentinel = object()

logger = logging.getLogger(__name__)
streamhandler = None

ESC = '\033['

RED_PREFIX = ESC + '38;5;9m'
RED_SUFFIX = ESC + '0m'

LOG_PREFIX = '\033[48;5;7mLOG\033[0m '
LOG_PREFIX_DGB= '\033[48;5;7mDBG\033[0m '
LOG_PREFIX_INFO = '\033[48;5;7mNFO\033[0m '
LOG_PREFIX_WARN = '\033[48;5;7mWRN\033[0m '
LOG_PREFIX_ERROR = '\033[48;5;7mERR\033[0m '

DEBUG_PREFIX = ESC + '38;5;6m'
DEBUG_SUFFIX = ESC + '0m'
INFO_PREFIX = ESC + '38;5;12m'
INFO_SUFFIX = ESC + '0m'
WARNING_PREFIX = ESC + '38;5;13m'
WARNING_SUFFIX = ESC + '0m'
ERROR_PREFIX = ESC + '38;5;9m'
ERROR_SUFFIX = ESC + '0m'
CRITICAL_PREFIX = ESC + '38;5;5m'
CRITICAL_SUFFIX = ESC + '0m'


if config.get('qapp', False):        
    filehandler = RotatingFileHandler(f'stderr.log', maxBytes=1024*1024, encoding='UTF-8',backupCount=5)
    filehandler.setLevel(config.get('logging_level_logfile', 'DEBUG'))    
    logging.root.addHandler(filehandler)
    
    
class StreamRouter(object):
    '''
    Pass the calls to a threading dependent stream
    '''
    
    def __init__(self):
        self.streams = dict()
        self.backup_stream = sys.__stdout__
    
    @property
    def stream(self):
        ident = threading.get_ident()
        
        if ident in self.streams.keys():       
            return self.streams[ident]
            
        else:
            return self.backup_stream
    
    def route_stream(self, stream, ident=None):  
        if ident is None:
            ident = threading.get_ident()                    
        self.streams[ident] = stream
        
    def unregister(self, ident=None):  
        if ident is None:
            ident = threading.get_ident()
        self.streams.pop(ident)
        
    def copy_to_thread(self, to_tid, from_tid=None):
        from_tid = from_tid or threading.get_ident()
        self.streams[to_tid] = self.streams[from_tid]
        
    def __getattr__(self, attr):
        return getattr(self.stream, attr)
        
    def __dir__(self):
        return dir(self.stream)
            
            
class StdOutRouter(StreamRouter):
    def __init__(self):
        super().__init__()
        self.backup_stream = sys.__stdout__
    
    
class StdErrRouter(StreamRouter):
    def __init__(self):
        super().__init__()
        self.backup_stream = sys.__stderr__
        
        
class GhStreamHandler(Handler):
    def __init__(self, stream):
        super().__init__()
        self.stream = stream
        self.set_name('ghstream')
        
        if not config['console'].get('logformat') is None:
            formatter = logging.Formatter(config['console'].get('logformat'))            
            self.setFormatter(formatter)        
        
    def setStream(self, stream):
        self.stream.flush()
        self.stream = stream

    def emit(self, record):            
        text = self.format(record)               

        if record.levelno <= logging.DEBUG:
            self.stream.write(f'{LOG_PREFIX_DGB}{DEBUG_PREFIX}{text}{DEBUG_SUFFIX}\n')
        elif record.levelno <= logging.INFO:
            self.stream.write(f'{LOG_PREFIX_INFO}{INFO_PREFIX}{text}{INFO_SUFFIX}\n')            
        elif record.levelno <= logging.WARNING:
            self.stream.write(f'{LOG_PREFIX_WARN}{WARNING_PREFIX}{text}{WARNING_SUFFIX}\n')
        elif record.levelno <= logging.ERROR:
            self.stream.write(f'{LOG_PREFIX_ERROR}{ERROR_PREFIX}{text}{ERROR_SUFFIX}\n')
        elif record.levelno <= logging.CRITICAL:
            self.stream.write(f'{LOG_PREFIX}{CRITICAL_PREFIX}{text}{CRITICAL_SUFFIX}\n')            
        else:        
            self.stream.write(f'LOG {text}')

        try:
            if record.levelno >= logging.WARNING:
                gui.console.show_me()
        except:
            pass


class PopupHandler(Handler):
    def emit(self, record):
        #Do not popup outside the main gui thread
        #Should it not be better to test console thread ?
        #Otherwise, errors in Qt Threads, will not popup
        if gui.qapp is None: return
        
        text = self.format(record)

        if record.levelno == logging.ERROR:        
            gui.dialog.msgbox(text, 'Error', 'error')            
        elif record.levelno == logging.CRITICAL:
            gui.dialog.msgbox(text, 'Critical', 'error')           


def enable_ghstream_handler():    
    global streamhandler
    streamhandler = GhStreamHandler(sys.stdout)
    streamhandler.setLevel(config.get('logging_level_console', 'WARNING'))
    logging.root.addHandler(streamhandler)       


class FlushReducer(object):
    def __init__(self, flusher):
        self.q = Queue()
        self.flusher = flusher
        self.thread = threading.Thread(target=self.reduce, name='FlushReducer', daemon=True)
        self.thread.start()
        
    def __call__(self):
        self.q.put(1)
        
    def reduce(self):
        while True:
            t = self.q.get()
            if t is sentinel:
                return
            time.sleep(0.01)
            self.q.queue.clear()
            self.flusher()
            
    def close(self):
        #wait on an empty queue
        while not self.q.empty():
            time.sleep(0.01)
        self.q.put(sentinel)

        
class FlushPipeStream(io.TextIOBase):
    def __init__(self, streamqueue, flusher):
        self.streamqueue = streamqueue
        self.echo = None
        self.echo_prefix = ''
        self.echo_enabled = False
        self.flusher = FlushReducer(flusher)
        
        
    def write(self, text):
        self._write_mode(text, config['stdoutmode'])

    def ansi(self, text):
        self._write_mode(text, 'ansi')
        
    def _write_mode(self, text, mode, prefix='', suffix=''):            
        if mode == 'ansi':
            text_fmt = f'{prefix}{text}{suffix}'
            
        self.streamqueue.put((mode, text_fmt))
        
        if not self.echo is None and self.echo_enabled:
            self.echo._write_mode(text_fmt, mode, f'{self.echo_prefix}{prefix}', suffix)
            
        self.flush()               
        
    def flush(self): 
        self.flusher()      


class ErrLogStream(io.TextIOBase):
    def __init__(self):
        self.line_cache = ''      
        
    def write(self, text):        
        self.line_cache += text
        
        if text.endswith('\n'):        
            logger.error(self.line_cache.rstrip('\n'))
            self.line_cache = ''        

        
class ProcessStdInput(io.TextIOBase):   
    stdin_queues = dict()   
    
    def __init__(self, stdin_queue=None):
        self.stdin_queue = stdin_queue
        
    def close(self):
        pass
        
    def read(self, timeout=None):
        ident = threading.get_ident()
        
        if ident in ProcessStdInput.stdin_queues.keys():
            text = ProcessStdInput.stdin_queues[ident].get(timeout=timeout)                        
            return text
        else:
            return sys.__stdin__.read()