import collections
import importlib
import pprint
import logging
import sys

from qtpy.QtWidgets import *
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy import QtCore, QtGui

from .. import gui

from ..panels.base import BasePanel

from .laystruct import LayoutStruct
from .dockwidgets import DockContainer, DockTab, DockTag
from .overlay import DockOverlay, HoverButton

from ..utils.z_order import get_z_values

logger = logging.getLogger(__name__)

class DockManager(object):
    def __init__(self, panels, qapp):
        self.panels = panels
        self.qapp = qapp
        self.containers = dict()
        self.layoutstructs = dict()
        self.overlays = []
        self.newWindow = lambda name, parentName: gui.qapp.newWindow(name, parentName)
        self.deleteWindow = lambda w: gui.qapp.deleteWindow(w)
        self.perspectives = collections.OrderedDict()
        self.bindGroups = dict()
        
        HoverButton.load_icons()
        
    def new_container(self, parent=None, name='main'):
        container = DockContainer(self, parent, name)
        self.containers[name] = container
        return container
        
    def add_button_to_bindgroup(self, category, panid, button):
        if not category in self.bindGroups.keys():
            self.bindGroups[category] = QButtonGroup(self.qapp)
        
        #If old button can still exist
        #PySide2 doesn't seem to overwrite it, so remove it first
        existingButton = self.bindGroups[category].button(panid)
        if not existingButton is None:
            self.bindGroups[category].removeButton(existingButton)
            
        self.bindGroups[category].addButton(button, panid)
        
    def detach_all(self):
        for category, panels in self.panels.items():        
            for panid, panel in panels.items():
                panel.detach()
                
        for name, container in self.containers.items():
            container.compact()
            
    def get_container(self, category, panid):
        for container in self.containers.values():
            if (category, panid) in container.panelIds:
                return container
        return None

    def get_layout_struct_from_containers(self):
        self.layoutstructs.clear()
        for name, container in self.containers.items():
            self.layoutstructs[name] =  container.get_layout_struct()
        return self.layoutstructs
        
    def show_overlays(self, window, insert_node, allWindows=True):
        if allWindows:
            for container in self.containers.values():
                if not container.isVisible() or container.parent() is window: continue
                overlay = DockOverlay(container, tool=False)
                overlay.show_and_insert(window, insert_node)
                self.overlays.append(overlay)
        else:
            container = window.parent().container
            overlay = DockOverlay(container, tool=False)
            overlay.show_and_insert(window, insert_node)
            self.overlays.append(overlay)            
            
        return len(self.overlays)
        
    def drop_in(self, container, hide=True, allWindows=False):
        window = container.parent()
        if window.parent() is None:
            allWindows = True
        if hide: window.hide()
        layout = container.get_layout_struct()
        layout.compact()
        self.show_overlays(window, layout.root, allWindows)
            
    def distribute(self):
        for container in self.containers.values():
            container.distribute()           
        
    def hide_overlays(self):
        for overlay in self.overlays:
            overlay.hide()
            overlay.deleteLater() 
            
        self.overlays.clear()               
            
    def new_window_on_panel(self, panel, parentName=None):
        layout = LayoutStruct()
        layout.root = {'type': 'panel', 'category': panel.category, 'id': panel.panid}
        return self.new_window_using_layout(layout, panel.width(), panel.height(), parentName=parentName)
            
    def new_window_using_layout(self, layout, width=640, height=480, parentName=None):
        w = self.newWindow(None, parentName)
        geo = w.geometry()
        geo.setWidth(width)
        geo.setHeight(height)
        w.setGeometry(geo)
        layout.compact()
        w.container.update_layout(layout)
        w.show()
        return w
        
    def get_perspective(self):        
        perspective = dict()
        perspective['panels'] = []
        perspective['windows'] = []
        
        for category in self.panels.keys():            
            for panid, panel in self.panels[category].items():            
                panelinfo = dict()                
                panelinfo['id'] = panid
                panelinfo['category'] = category
                panelinfo['module'] = type(panel).__module__
                panelinfo['qualname'] = type(panel).__qualname__
                #panelinfo['basewindow'] = panel.baseWindowName
                panelinfo['title'] = panel.windowTitle()
                
                bindings = []
                
                for bindcategory, bindpanid in panel.bindings:
                    binding = dict()
                    binding['category'] = bindcategory
                    binding['id'] = bindpanid
                    bindings.append(binding)
                    
                panelinfo['bindings'] = bindings                
                perspective['panels'].append(panelinfo)        
        
        for name, container in self.containers.items():
            #window = container.parent()
            ls = container.get_layout_struct()
            ls.compact()
            visible = container.parent().isVisible()
            perspective['windows'].append({'name': name, 'docks': ls.root, 'visible': visible})
            
        return perspective

    def set_perspective(self, perspective):
        self.detach_all()
        
        panels = perspective['panels']
        postlayinits = []
        
        #Create panels
        for panelinfo in panels:
            category = panelinfo['category']
            panid = panelinfo['id']
            module = panelinfo['module']
            qualname = panelinfo['qualname']            
            #base_window_name = panelinfo['basewindow']
            
            id_exists = self.panels.id_exists(category, panid)
            
            tmp = importlib.import_module(module)
            for attr in qualname.split('.'):
                tmp = getattr(tmp, attr) 

            Cls = tmp           

            if id_exists:
                panel = self.panels[category][panid]
                if isinstance(panel, Cls):
                    continue
                else:
                    # Delete of this existing panel
                    # Or keep reference to it in some old_panels dictionary?
                    # So the user can still decide what to do with it
                    # What to do with the panid, rename it available id not used in this perspective?
                    # What to do with the bindings
                    # Or just remap the conflicting panid to a fresh panid
                    logger.warn(f'Panel {category} {panid} already exists but is of wrong class {type(panel)}')
                    persp_cat_panids = set(tmppanel['id'] for tmppanel in panels if tmppanel['category'] == category)
                    exist_cat_panids = set(self.panels[category].keys())
                    logger.debug(f'Perspective panids of {category}: {persp_cat_panids}')
                    logger.debug(f'Existing panids of {category}: {exist_cat_panids}')
                    continue                    
                     
            panel = self.panels.new_panel(Cls, None, panid, floating=True) 
            
            if hasattr(panel, 'postLayoutInit'):
                postlayinits.append(panel.postLayoutInit)

        #Setup of bindings
        for panelinfo in panels:
            category = panelinfo['category']
            panid = panelinfo['id']            
            panel = self.panels[category][panid]
            for binding in panelinfo['bindings']:
                bindcategory = binding['category']
                bindpanid = binding['id']
                panel.addBindingTo(bindcategory, bindpanid)      
        
        for window in perspective['windows']:            
            ls = LayoutStruct()
            ls.root = window["docks"]
            visible = window.get('visible', True)
            
            #container = self.qapp.windows['main'].container
            winname = window['name']
            if winname in self.qapp.windows.keys():
                window = self.qapp.windows[winname]
            else:
                window = self.newWindow(None, None)
            window.container.update_layout(ls)
            if visible:
                window.show()
                window.raise_()
            else:
                window.hide()            
        
        #Put all the floating pannels together in tabs and one seperate window
        floating_panels = []
        for category in self.panels.keys():
            for panid, panel in self.panels[category].items():
                if panel.parent() is None:
                    node = {'type': 'panel', 'category': category, 'id': panid}
                    floating_panels.append(node)                  
        
        if len(floating_panels) > 0:
            layout = LayoutStruct()
            layout.root = dict()
            layout.root['type'] = 'layout'
            layout.root['category'] = 'tab'
            layout.root['id'] = 1
            layout.root['items'] = floating_panels
            win = self.new_window_using_layout(layout)
            win.hide()            
            
        gui.qapp.deleteEmptyWindows(True)     

        for postLayoutInit in postlayinits:
            postLayoutInit()

        self.panels.reselect_all()
