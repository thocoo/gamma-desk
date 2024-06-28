import threading
import sys, os
import ctypes
from collections import OrderedDict
import logging
import importlib
import pprint
from pathlib import Path

import numpy as np

from qtpy import QtGui, QtWidgets, QtCore, API_NAME
from qtpy.QtCore import Qt

if API_NAME in ['PySide6']:
    from qtpy.QtGui import QGuiApplication

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
        return self.get(category)
        
    def get(self, category, default=None):
        return self.panels.get(category, default)

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
        panel = self.selected(category, panidpos)
        if panel is None:
            return None
        else:
            return panel.panid

    def new(self, category, paneltype=None, windowname=None, size=None, *args, **kwargs):
        image_classes = self.classes_of_category(category)
        if paneltype is None:
            ImageClass = next(iter(image_classes.values()))
        else:
            ImageClass = image_classes[paneltype]
        panel = self.new_panel(ImageClass, windowname, None, size=size, args=args, kwargs=kwargs)
        return panel

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
            panel = self.new(category, defaulttype, parentName, *args, **kwargs)

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

    def new_panel(self, PanelClass, parentName=None, panid=None, floating=False, title=None,
            position=None, size=None, args=(), kwargs={}):

        if parentName is None:
            activeWindow = self.qapp.activeWindow()
            if isinstance(activeWindow, MainWindow):
                parentName =  activeWindow.name

        panel = PanelClass(None, panid, *args, **kwargs)
        if not title is None:
            panel.long_title = title
        
        if not size is None:
            panel.setGeometry(0, 0, size[0], size[1])
            
        #panel.show()

        if floating:
            window = panel
        else:
            window = self.ezm.new_window_on_panel(panel, parentName)
            #window.activateWindow()  

        if position is None:
            position = self.place_window(window, panel.category)

        window.move(position)                   
        panel.select()

        return panel

    def place_window(self, window, category):        
        # screen = QtWidgets.QDesktopWidget().screenNumber(self.qapp.windows['main'])
        # desktop_rect = QtWidgets.QDesktopWidget().availableGeometry(screen)
        
        main_screen = self.qapp.windows['main'].screen()
        desktop_rect = main_screen.availableGeometry()        
        
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
        
        visible = False
        
        # Check if the window is fully visible on any screen.
        if API_NAME in ['PySide6']:
            screens = QGuiApplication.screens()
            for screen in screens:
                if screen.availableGeometry().contains(window_rect):
                    visible = True
            
        else:
            for screen in range(QtWidgets.QDesktopWidget().screenCount()):        
                if QtWidgets.QDesktopWidget().availableGeometry(screen).contains(window_rect):
                    visible = True
            
        if not visible:
            position = desktop_rect.topLeft()

        return position

    def get_menu_action(self, category, panid, menutrace, refresh=True):
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
            
        if panid is None:
            return

        panel = self[category][panid]

        return getMenuAction(panel.menuBar(), menutrace, refresh=refresh)


    def removeBindingsTo(self, category, panid):
        for c, panels in self.items():
            for p, panel in panels.items():
                if (category, panid) in panel.bindings:
                    panel.removeBindingTo(category, panid)
