import sys
import threading
import logging
from queue import Queue

from qtpy.QtCore import QObject, QMetaObject, Slot, Qt
from qtpy.QtWidgets import QWidget

class ReturnLock:

    """
    Lock and return value object used to pass the return value on SignalCalls.
    """

    def __init__(self):
        self.lock = threading.Lock()
        self.lock.acquire()
        
    def waitOnReturn(self):
        self.lock.acquire()
        return self.value
        
    def releaseReturn(self, value):
        self.value = value
        self.lock.release()
        
    def locked(self):
        return self.lock.locked()

class HandOver(QObject):
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.signal_call_queue = Queue()                   
        
    def send(self, block=True, func=None, *args, **kwargs):
        """
        :param block: wait on the func to return
        :param func: the reference to the function to be called by the eventloop
        :param ``*args``: unnamed arguments for the function
        :param ``**kwargs``: key word arguments for the function
        """
        returnlock = ReturnLock()
        self.signal_call_queue.put((returnlock, func, args, kwargs))         
        QMetaObject.invokeMethod(self, "receive", Qt.QueuedConnection)           
        if block:
            returnlock.waitOnReturn()            
            return returnlock.value
        else:
            return returnlock                
        
    @Slot()    
    def receive(self):
        """
        Receive returnlock, func, args, kwargs from signal_call_queue
        """
        (returnlock, func, args, kwargs) = self.signal_call_queue.get()
        returnvalue = None
        try:
            returnvalue = func(*args, **kwargs)
        except:
            logging.error(f'Error during gui call {func} {args} {kwargs}')
            raise
        finally:
            returnlock.releaseReturn(returnvalue)   