import sys
import threading
from multiprocessing import Queue
import functools
import importlib
import types
import pickle
import logging
import pathlib
import time

import numpy as np

from ..utils.funccom import find_nested_func
from ..utils.imconvert import qimage_to_ndarray

from .conf import config

if sys.platform == "win32":
    from ..utils.keypress import PressKey, ReleaseKey
else:
    PressKey = None
    ReleaseKey = None

logger = logging.getLogger(__name__)

if config.get('sphinx', False):
    #https://stackoverflow.com/questions/28366818/preserve-default-arguments-of-wrapped-decorated-python-function-in-sphinx-docume
    def wraps(original_func):
       wrap_decorator = functools.wraps(original_func)
       def re_wrapper(func):
           wrapper = wrap_decorator(func)
           poorman_sig = original_func.__code__.co_varnames[
                             :original_func.__code__.co_argcount]
           wrapper.__doc__ = "{} ({})\n\n{}".format (
                original_func.__name__, ", ".join(poorman_sig),
                wrapper.__doc__) 
           return wrapper
       return re_wrapper           
else:           
    wraps = functools.wraps
    
def StaticGuiCall(func):
    #Decorator for pushing the function call through a queue
    #func is the function of the decorated method, not the method itself?    
    @staticmethod
    @wraps(func)
    def caller(*args, **kwargs):        
        return gui.gui_call(func, *args, **kwargs)
    return caller
    
    
class RedBull(object):
    def __init__(self, interval=60):       
        self.interval = interval
        self.actives = []
        self.timer_thread = None
        #Function Key 15
        self.keycode = 0x7E  

    def enable(self, interval=None):        
        if len(self.actives) == 0:
            self.start(interval or self.interval)
        else:
            self.stop() 
            self.start(interval or self.interval)
                                                               
    def disable(self):
        self.stop()
            
    def start(self, interval):
        self.timer_thread = threading.Thread(target=self.loop, args=(interval,))
        self.timer_thread.start()
        
    def stop(self):
        self.actives.clear()
        self.timer_thread = None
            
    def loop(self, interval):
        ident = threading.get_ident()
        self.actives.append(ident)
        while True:
            time.sleep(interval)
            if not ident in self.actives: break
            self.do()
        
    def do(self):
        PressKey(self.keycode)  
        ReleaseKey(self.keycode)       
        
        
class FakeGui(object):
    
    def show(self, *args, **kwargs):
        print(*args)
    
        
class GuiProxyBase(object):
    category = None
    
    @classmethod
    def derivedClasses(cls):
        l = []
        for SubClass in cls.__subclasses__():
            l.extend(SubClass.derivedClasses())
            l.append((SubClass.category, SubClass))
            
        if cls is GuiProxyBase:
            result = dict()
            
            for category, Cls in l:
                if not category in result.keys():
                    result[category] = []
                result[category].append(Cls)
            return result
        else:
            return l
    
    
    @classmethod
    def menu(cls, action_names, *args, **kwargs):
        """
        Call a certain menu item of the panel
        
        :param list action_names: Example ['File', 'New...']
        :param ``*args``: Positional arguments of the menu call
        :param ``**kwargs``: Keyword arguments of the menu call
        """
        return gui.menu_trigger(cls.category, None, action_names, *args, **kwargs)

    
    @classmethod
    def new(cls, paneltype=None, windowname=None, *args, **kwargs):
        return GuiProxyBase._new(cls.category, paneltype, windowname, *args, **kwargs)
        
        
    @StaticGuiCall        
    def _new(category, paneltype=None, windowname=None, size=None, *args, **kwargs):
        return gui.qapp.panels.new(category, paneltype, windowname, size=size, *args, **kwargs)

    
    @classmethod
    def selected(cls):
        """
        Return the panel id of the selected panel if this category.
        """
        category = cls.category
        return GuiProxyBase._selected_panid_of_category(category)
        
        
    @StaticGuiCall
    def _selected_panid_of_category(category):
        return gui.qapp.panels.selected(category, panel=False)
        
        
    @classmethod
    def close(Cls, panid=-1):
        """
        Close the selected panel of the category
        """   
        return Cls._close_panel_of_category(panid, Cls.category)
        
        
    @StaticGuiCall
    def _close_panel_of_category(panid, category):        
        panel = gui.qapp.panels.selected(category, panid)
        if not panel is None:
            panel.close_panel()
            return True
        else:
            return False
            
    @classmethod
    def grab(cls):
        return cls._panel_grab(cls.category)
                 
    @StaticGuiCall
    def _panel_grab(category):
        panel = gui.qapp.panels.selected(category)
        pixmap = panel.grab()
        image = pixmap.toImage()
        arr = qimage_to_ndarray(image)        
        return arr
        

    

#Note that a embeded function is also be static if closure is None            
STATIC = 1   

#Embeded functions with closure not None
ENCLOSED = 2

#Method on object
METHOD = 4

                               
class GuiProxy(object):    
    """
    Communication channel to the gui
    Master and Slave
    Across Procecess and Threads
    """
    
    push_list = []
    
    def __init__(self, qapp=None, master_call_queue=None, master_return_queue=None, process_ready_call=None):
        """
        In case of multiprocessing, there is a gui instance at the master process
        for every child process and an instance at the child process
        
        :param qapp: None in case of child process
        :type qapp: QApplication or None
        :param bool process: True in case of multi processing
        :param multiprocessing.queue master_queue: The event queue from the master process
        """
        self.hooks = dict()
        self.reg_obj = dict()
        self.proxies = dict()
        
        self.block = True
        self._qapp = qapp
                
        self.call_queue = master_call_queue
        self.return_queue = master_return_queue     

        if not process_ready_call is None:
             self.set_func_hook(-2, process_ready_call) 
        
        if not qapp is None:        
            if not self.call_queue is None:
                self.pass_thread = threading.Thread(target=self._pass_to_eventloop, name=f'Handover-{id(self)}', daemon=True)
                self.pass_thread.start()
                
        self.redbull = RedBull()
        self.refresh_proxies()

    @property
    def qapp(self):
        """
        The QApplication instance. Is only visible in the gui thread.
        """
        #Hide it also for threads in the gui app which are not the main
        #User should not use it directly, only by gui_call
        if self.is_main():
            return self._qapp
        else:
            return None
        
    def refresh_proxies(self):
        """
        Add all currently imported Gui Proxies.
        
        :meta private:
        """
        catclasses = GuiProxyBase.derivedClasses()
        for category, classes in catclasses.items():
            proxy = classes[0]()
            name = proxy.attach(self)
            if not name is None:
                self.proxies[name] = proxy
            
    def set_func_hook(self, key, func):
        """
        :meta private:
        """
        self.hooks[key] = func    

    def register_object(self, obj):
        #This is supposed to happen only in the gui thread
        id_obj = id(obj)
        self.reg_obj[id_obj] = [obj] + self.reg_obj.get(id_obj, [])
        return id_obj
        
    def retrieve_object(self, key):        
        lst = self.reg_obj[key]
        func_id = lst.pop()
        if len(lst) == 0:
            self.reg_obj.pop(key)
        return func_id

    def is_main(self):
        return (not self._qapp is None and threading.currentThread().name == 'MainThread')

    def encode_func(self, func, register=False):
        if isinstance(func, (int, tuple)):
            #It is already encoded
            func_id = func
            
        elif isinstance(func, (types.FunctionType, type)):                 
            module = func.__module__
            qualname = func.__qualname__        
            
            if func.__closure__ is None:
                func_id = STATIC, module, qualname
            else:
                closere_id = self.register_object(func.__closure__)
                func_id = ENCLOSED, module, qualname, closere_id            
            
        elif isinstance(func, (types.MethodType, type)):                 
            module = func.__module__
            qualname = func.__qualname__
            self_key = self.register_object(func.__self__)
            func_id = METHOD, module, qualname, self_key
            
        else:
            raise AttributeError(f'Type of {func} is not valid')
            func_id = func.__name__            
                   
        return func_id
            
    def decode_func(self, func_id):        
        if isinstance(func_id, int):
            #For some limit cases, this a a quicker decoding
            #Used for stdout flushing and process_ready
            func = self.hooks[func_id] 
                
        elif isinstance(func_id, tuple):
            lib = importlib.import_module(func_id[1])            
            attrs = func_id[2]
            parts = attrs.split('.')
                
            if func_id[0] in [STATIC, ENCLOSED]:
                tmp = lib
                closure = None if func_id[0] == STATIC else self.retrieve_object(func_id[3])
                for i, attr in enumerate(parts):
                    if attr == '<locals>':
                        tmp = find_nested_func(tmp, parts[i+1], lib.__dict__, closure)
                        break
                    else:
                        tmp = getattr(tmp, attr)
                
                func = tmp                             
                
            elif func_id[0] == METHOD:
                obj = self.retrieve_object(func_id[3])
                tmp = lib                
                for i, attr in enumerate(parts):
                    tmp = getattr(tmp, attr)                    
                func = types.MethodType(tmp, obj)                                   
                
        else:
            #already decoded, was not encoded
            func = func_id                             
                
        return func    

    def gui_call(self, func, *args, **kwargs):
        if self.is_main():
            func = self.decode_func(func)
            return func(*args, **kwargs)
            #return self._qapp.handover.send(self.block, func, *args, **kwargs)
            
        return self._call(func, *args, **kwargs)        
            
    def _call(self, func, *args, **kwargs):                     
        return self._call_base(self.block, func, *args, **kwargs)            

    def _call_no_wait(self, func, *args, **kwargs):
        return self._call_base(False, func, *args, **kwargs)
            
    def _call_base(self, wait, func, *args, **kwargs):                    
        if self.call_queue is None:
            #Multi Threading Child
            #Direct handover to eventloop
            func = self.decode_func(func)
            return self._qapp.handover.send(wait, func, *args, **kwargs)
            
        else:
            #Multi Processing Child
            #Handover to Gui Process                
            func = self.encode_func(func)
                
            if wait:
                self.call_queue.put((True, func, args, kwargs))
                value = self.return_queue.get()
                return value
                
            else:
                self.call_queue.put((False, func, args, kwargs))
                return None
        
    def _pass_to_eventloop(self):
        """
        Receive func, args, kwargs from call_queue
        and handover to event loop.
        
        :meta private:
        """
        while True:
            backval, func, args, kwargs = self.call_queue.get()
            func = self.decode_func(func)
            value = self._qapp.handover.send(True, func, *args, **kwargs)
            if backval:
                self.return_queue.put(value)                     
    
    @StaticGuiCall    
    def get_panel_ids(category):
        """
        Returns all current panal ids of a category.
        The last one is the selected one.
        
        :returns: current panal ids 
        :rtype: list
        """
        if category in gui.qapp.panels.keys():
            return list(gui.qapp.panels[category].keys())
        else:
            return []


    @StaticGuiCall    
    def load_layout(name='console'):
        gui.qapp.panels.restore_state_from_config(name)        


    def show(self, *args, **argv):
        """
        Shows a object in an suitable panel

        You can give more then one object to display, multiple viewers will be created.

        :param int select: selects which viewer shows the object (start with 1! 0 in GH1)
            negative numbers stands for last selected, or the selected before that, or before that                 
        """        
        objcount = len(args)
        panids = argv.get('select', range(-objcount, 0))
        panid = None
        
        for obj, panid in zip(args, panids):
            if isinstance(obj, np.ndarray):   
                self.img.select(panid)              
                panid = self.img.show(obj)                                                                                 
                
        return panid

    
    @property
    def vs(self):
        """
        The shared array on the current image viewer
        Note that the data is on shared memory.
        ``vs[:]`` or ``vs.ndarray`` to view it as a real numpy array
        """
        try:
            return self.img.vs
        except:
            return None
             
    @property  
    def vr(self):
        """
        The selection interface of the current image viewer
        """
        try:
            return self.img.vr
        except:
            return None
            
            
    @property  
    def roi(self):
        """
        The named roi interface of the current image viewer
        """
        try:
            return self.img.roi
            
        except:
            return None
            

    @StaticGuiCall 
    def menu_trigger(category, pandid, action_names, *args, **kwargs):
        """
        Trigger a menu action of a panel.
        
        :param str category: Example 'image'
        :param int id: Example 1
        :param list action_names: Example ['File', 'New...']
        """
        try:
            action = gui.qapp.panels.get_menu_action(category, pandid, action_names, refresh=False)                   
        except KeyError:    
            logger.error(f'Menu action {action_names} not found')
            return
        if len(args) == len(kwargs) == 0:
            action.setData(None)
        else:
            action.setData({'args':args, 'kwargs': kwargs})
        retval = action.trigger()
        action.setData(None)
        return retval

    @StaticGuiCall 
    def history(count=20):   
        """
        The command history
        
        :param int count: Show the last count elements   
        
        :returns: Command history as list
        :rtype: list
        """
        return gui.qapp.history.tail(count)     

    @StaticGuiCall 
    def push(obj):
        """
        Push an object on the gui data stack
        
        :param object obj: A pickable object
        """
        GuiProxy.push_list.append(obj)
        
    @StaticGuiCall       
    def pull():
        """
        Pull and object from the gui data stack
        
        :returns: The object  
        """
        return GuiProxy.push_list.pop(0)        
        
    @StaticGuiCall              
    def exit():
        """
        Exit Gamma Desk.
        """
        gui.qapp.quit()        
        

class GuiMap(object):
    gui_proxies = dict()
    redirects = dict()
    
    def __init__(self):
        pass        
        
    def load_layout(self, layout='base'):
        self._gui_proxy.load_layout(layout)
        for tid, guiinst in self.gui_proxies.items():
            guiinst.refresh_proxies()        
        
    @property
    def _gui_proxy(self):
        ident = threading.get_ident()
        ident = GuiMap.redirects.get(ident, ident)        
        return GuiMap.gui_proxies.get(ident, None)
        
    def valid(self):
        return not self._gui_proxy is None
        
    def __dir__(self):
        return self._gui_proxy.__dir__()        
        
    def __repr__(self):
        return self._gui_proxy.__repr__()
        
    def __str__(self):        
        return self._gui_proxy.__str__()        
    
    def __getattr__(self, attr):
        return getattr(self._gui_proxy, attr)
        
    def __setattr__(self, attr, value):
        return setattr(self._gui_proxy, attr, value)

gui = GuiMap()

def register_objects_in_gdesk_init():
    import gdesk
    gdesk.GuiMap = GuiMap
    gdesk.gui = gui
    gdesk.StaticGuiCall = StaticGuiCall