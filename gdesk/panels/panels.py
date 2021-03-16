import threading
import sys, os
import ctypes
from collections import OrderedDict
import logging
import importlib
import pprint
from pathlib import Path

import numpy as np

from qtpy import QtGui, QtWidgets, QtCore
from qtpy.QtCore import Qt

from .. import config, gui, __release__
from ..core import conf

from .base import BasePanel
from .window import MainWindow
from ..ezdock.ezdock import DockManager
from ..ezdock.laystruct import LayoutStruct
from ..utils import new_id_using_keys
from ..gcore.utils import getMenuAction

respath = Path(config['respath'])
sck = config['shortcuts']
logger = logging.getLogger(__name__)

class Panels(object):
    def __init__(self, qapp):
        self.panels = OrderedDict()               
        self.ezm = DockManager(self, qapp)        
        self.qapp = qapp
            
    def keys(self):
        return self.panels.keys()
            
    def __getitem__(self, category):
        return self.panels[category]
        
    def id_exists(self, category, panid):
        if not category in self.keys():
            self.panels[category] = OrderedDict()
            
        return panid in self.panels[category].keys()
        
    def new_id(self, category):
        return int(new_id_using_keys(tuple(self[category].keys())))

    def items(self):
        for item in self.panels.items():
            yield item
        
    def move_to_end(self, widget, category=None):                           
        if not category is None:
            catpanels = self.panels[category]            
            panid = next((k for k,v in panels.items() if v is widget), None)
        
        else:
            for category, catpanels in self.panels.items():        
                panid = next((k for k,v in catpanels.items() if v is widget), None)
                if not panid is None: break
            else:
                panid = None
                category = None
        
        if not panid is None:
            catpanels.move_to_end(panid)
            self.panels.move_to_end(category)
        
        return panid, category

    def __iter__(self):
        for category in self.keys():
            yield category, self[category]
            
    def get_active_panid(self, category, panidpos=-1):
        return self.selected(category, panidpos).panid
        
    def select_or_new(self, category, panid=None, defaulttype='basic', parentName='main', args=(), kwargs={}):
        """
        If panid < 0, -1: select the active panel, -2: selected before that, ...
        panid > 0: select the panel if exists, otherwise a new with that number
        """
        
        if not panid is None and panid < 0:
            panel = self.selected(category, panid)
        
        elif category in self.keys():
            panel = self[category].get(panid, None)
            
        else:
            panel = None
            
        if panid is not None and panid < 0:
            panid = None
            
        if panel is None:
            image_classes = self.classes_of_category(category)
            ImageClass = image_classes[defaulttype]
            panel = self.new_panel(ImageClass, parentName, panid, args=args, kwargs=kwargs)
            
        panel.select()      
            
        return panel
        
    def selected_category(self):
        return tuple(self.panels.keys())[-1]
            
    def selected(self, category, panidpos=-1, panel=True):
        assert panidpos < 0
        
        if category in self.keys():
            panids = tuple(self[category].keys())
        else:
            return None
        
        if abs(panidpos) <= len(panids):
            panid = panids[panidpos]
            if panel:
                panel = self[category][panid]
                return panel
            else:
                return panid
        else:
            return None            
        
    def reselect_all(self):
        for category in list(self.keys()):
            panel = self.selected(category)            
            if not panel is None:
                #logger.info(f'Selecting {category}: {panel.panid}')
                panel.select()

    def restore_state_from_config(self, layout_name):
        if isinstance(layout_name, int):
            layout_name = config['shortcuts']['layout'][str(layout_name)]
        perspective = config['layout'][layout_name]
        self.ezm.set_perspective(perspective)  
        
    def classes_of_category(self, category):
        panelClasses = BasePanel.userPanelClasses()
        panelClassesCat = panelClasses.get(category, [])
        return dict([(Cls.panelShortName, Cls) for Cls in panelClassesCat])
        
    def new_panel(self, PanelClass, parentName=None, panid=None, floating=False, position=None, args=(), kwargs={}):
        
        if parentName is None:
            activeWindow = self.qapp.activeWindow()
            if isinstance(activeWindow, MainWindow):
                parentName =  activeWindow.name
            
        panel = PanelClass(parentName, panid, *args, **kwargs)
        panel.show()
        
        if floating:
            window = panel
        else:
            window = self.ezm.new_window_on_panel(panel, parentName)
            
        if position is None:                            
            position = self.place_window(window, panel.category)
            
        window.move(position)
            
            
        panel.select()
        
        return panel 

    def place_window(self, window, category):
        desktop_rect = QtWidgets.QDesktopWidget().availableGeometry()
        window_rect = window.frameGeometry()
        prior_panel = self.selected(category, -2)
        
        if not prior_panel is None:
            prior_rect = prior_panel.frameGeometry()
            topleft = prior_panel.mapToGlobal(QtCore.QPoint(0,0))
            prior_rect.moveTopLeft(QtCore.QPoint(topleft.x()+10, topleft.y()+10))
            center = prior_rect.center()
        else:
            center = desktop_rect.center()
            
        window_rect.moveCenter(center)
        position = window_rect.topLeft()
        
        if not desktop_rect.contains(window_rect):
            position = QtCore.QPoint(0,0)
        
        return position

    def get_menu_action(self, category, panid, menutrace):
        """
        Trigger a menu action of a panel.
        
        :param str category: Example 'image'
        :param int id: Example 1
        :param list menutrace: Example ['File', 'New Image']
        """
        
        if category is None:
            window = self.qapp.activeWindow()
            if not isinstance(window, MainWindow):
                raise KeyError('Action not found')
            category = window.activeCategory
        
        if panid is None:
            panid = self.get_active_panid(category)
            
        panel = self[category][panid]
        
        return getMenuAction(panel.menuBar(), menutrace)        
        
            
    def removeBindingsTo(self, category, panid):
        for c, panels in self.items():
            for p, panel in panels.items():
                if (category, panid) in panel.bindings:
                    panel.removeBindingTo(category, panid)
                    