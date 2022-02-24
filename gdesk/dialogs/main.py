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

from .. import config, gui, __release__, PROGNAME, DOC_HTML
from ..core import conf
from ..console import restart

from .about import AboutScreen
from ..panels.base import BasePanel
from ..ezdock.laystruct import LayoutStruct
from ..dicttree.widgets import DictionaryTreeDialog

logger = logging.getLogger(__name__)
respath = Path(config['respath'])

class NewPanelMenu(QtWidgets.QMenu):
    def __init__(self, parent=None, showIcon=False):
        super().__init__('New', parent)
        if showIcon:
            self.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'application_add.png')))

    @property
    def panels(self):
        return QtWidgets.QApplication.instance().panels

    def showEvent(self, event):
        self.showpos = QtGui.QCursor().pos()
        self.initactions()

    def initactions(self):
        self.clear()
        panelClasses = BasePanel.userPanelClasses()

        self.liveActions = []

        for category, catPanelClasses in panelClasses.items():
            catMenu = QtWidgets.QMenu(category)
            self.addMenu(catMenu)
            for panelClass in catPanelClasses:
                if not panelClass.userVisible: continue
                try:
                    panelShortName =  panelClass.panelShortName
                except:
                    panelShortName = 'unkown'

                action = QtWidgets.QAction(f'{panelShortName} <{panelClass.__qualname__}>')

                if hasattr(panelClass, 'classIconFile'):
                    action.setIcon(QtGui.QIcon(panelClass.classIconFile))

                action.triggered.connect(CachedArgCall(self.newPanel, panelClass, self.parent().windowName, self.showpos))
                catMenu.addAction(action)
                self.liveActions.append(action)

    def newPanel(self, panelClass, windowName, showpos=None):
        if panelClass.panelCategory == 'plot':
            import pylab
            fig = pylab.figure()
        else:
            self.panels.new_panel(panelClass, windowName)


class ShowMenu(QtWidgets.QMenu):
    def __init__(self, parent=None, showIcon=False):
        super().__init__('Panel', parent)
        if showIcon:
            self.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'application_get.png')))

    def showEvent(self, event):
        self.initactions()

    @property
    def panels(self):
        return QtWidgets.QApplication.instance().panels

    def preview(self):
        self.previews = PanelsFloatingPreviews()
        self.previews.preview()
        self.previews.exec_()

        self.previews.selectedPanel.select()
        self.previews.selectedPanel.show_me()

    def initactions(self):
        self.clear()

        self.liveActions = []

        action = QtWidgets.QAction(f'Previews...\t{config["shortcuts"]["panel preview"]}', triggered=self.preview)
        self.addAction(action)
        self.liveActions.append(action)
        self.addSeparator()

        for category in self.panels.keys():
            panels = self.panels[category]
            selected_panid = self.panels.selected(category, panel=False)
            for panid in sorted(panels.keys()):

                panel = self.panels[category][panid]
                action = QtWidgets.QAction(panel.windowTitle())
                action.triggered.connect(CachedArgCall(self.showPanel, panel))
                action.setCheckable(True)

                if panel.panid == selected_panid:
                    action.setChecked(True)
                else:
                    action.setChecked(False)

                self.addAction(action)
                self.liveActions.append(action)

    def showPanel(self, panel):
        panel.show_me()
        panel.select()

class WindowMenu(QtWidgets.QMenu):
    def __init__(self, parent=None, showIcon=False):
        super().__init__('Window', parent)
        if showIcon:
            self.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'application_double.png')))

    @property
    def windows(self):
        return QtWidgets.QApplication.instance().windows

    def showEvent(self, event):
        self.initactions()

    def preview(self):
        self.previews = WindowsFloatingPreviews()
        self.previews.preview()
        self.previews.exec_()

    def initactions(self):
        self.clear()

        self.liveActions = []

        action = QtWidgets.QAction(f'Previews...\t{config["shortcuts"]["window preview"]}', triggered=self.preview)
        self.addAction(action)
        self.liveActions.append(action)
        self.addSeparator()

        for window_name in self.windows.keys():
            window = self.windows[window_name]
            action = QtWidgets.QAction(window_name)
            action.triggered.connect(CachedArgCall(self.showWindow, window))
            self.addAction(action)
            self.liveActions.append(action)

    def showWindow(self, window):
        window.show()
        window.raise_()


class CachedArgCall(object):
    def __init__(self, caller, *args, **kwargs):
        self.caller = caller
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        self.caller(*self.args, **self.kwargs)


class LayoutMenu(QtWidgets.QMenu):
    def __init__(self, parent=None, showIcon=False):
        super().__init__('Layout', parent)
        if showIcon:
            self.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'layout_content.png')))

        self.initactions()

    @property
    def panels(self):
        return QtWidgets.QApplication.instance().panels

    def showEvent(self, event):
        self.initactions()

    def initactions(self):
        self.clear()

        action = QtWidgets.QAction('Save Layout...', self, triggered=self.saveLayout)
        self.addAction(action)
        self.addSeparator()

        self.addLayoutActions(self)

    def addLayoutActions(self, parent=None):
        shortcuts = dict((v,k) for k,v in config['shortcuts']['layout'].items())
        prefix = config['shortcuts']['layout']['prefix']

        for name, layout in config['layout'].items():
            shortcut = shortcuts.get(name, None)
            if shortcut is None:
                action = QtWidgets.QAction(name, parent)
            else:
                action = QtWidgets.QAction(f'{name}\t{prefix}{shortcut}', parent)
            caller = self.panels.restore_state_from_config
            action.triggered.connect(CachedArgCall(caller, name))
            parent.addAction(action)

    def saveLayout(self):
        layout_name = gui.dialog.getstring('Give it a name')
        if layout_name == '': return
        if layout_name == 'base':
            gui.dialog.msgbox(f"You can't overwrite {layout_name}", icon='warn')
        else:
            config['layout'][layout_name] = gui.qapp.panels.ezm.get_perspective()



class MainDialog(QtWidgets.QMainWindow):
    def __init__(self, panels):
        super().__init__()
        self.setWindowTitle(f'{PROGNAME} {__release__}')
        self.panels = panels
        self.tabs = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.panels_layout = PanelsLayout(self, panels)
        self.tabs.addTab(self.panels_layout, 'Layout')

        self.initMenu()
        self.callerWindow = None

    @property
    def qapp(self):
        return QtWidgets.QApplication.instance()

    @property
    def windowName(self):
        return None

    def initMenu(self):
        self.appMenu = self.menuBar().addMenu("&Application")

        act = QtWidgets.QAction("Restart", self,
            triggered=self.restart,
            statusTip=f"Restart {PROGNAME}",
            icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'recycle.png')))
        self.appMenu.addAction(act)

        act = QtWidgets.QAction("Exit", self, shortcut=QtGui.QKeySequence.Quit,
            statusTip=f"Exit {PROGNAME}",
            triggered=self.qapp.quit,
            icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'door_out.png')))

        self.appMenu.addAction(act)

        self.newMenu = NewPanelMenu(self)
        self.menuBar().addMenu(self.newMenu)

        self.showMenu = ShowMenu(self)
        self.menuBar().addMenu(self.showMenu)

        self.windowMenu = WindowMenu(self)
        self.menuBar().addMenu(self.windowMenu)

        self.layoutMenu = LayoutMenu(self)
        self.menuBar().addMenu(self.layoutMenu)

        self.configMenu = self.menuBar().addMenu("Config")
        self.configMenu.addAction(QtWidgets.QAction("View Config", self, triggered=self.showConfig,
            icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'page_gear.png'))))

        self.configMenu.addAction(QtWidgets.QAction("Save Config", self, triggered=self.saveConfig))
        
        #matplotlib.rcsetup.all_backends
        #'module://gdesk.matplotbe'

        self.helpMenu = self.menuBar().addMenu("Help")

        helpAct = QtWidgets.QAction("&Help", self, triggered=self.help)
        helpAct.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'help.png')))
        self.helpMenu.addAction(helpAct)

        aboutGhQtAct = QtWidgets.QAction(f"About {PROGNAME}", self, triggered=self.about)
        self.helpMenu.addAction(aboutGhQtAct)

        self.helpMenu.addAction(QtWidgets.QAction("License", self, triggered=self.license))

        infoGhQtAct = QtWidgets.QAction("Instance Info", self, triggered=self.info)
        infoGhQtAct.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'information.png')))
        self.helpMenu.addAction(infoGhQtAct)

        aboutQtAct = QtWidgets.QAction("About Qt", self, triggered=self.qapp.aboutQt)
        self.helpMenu.addAction(aboutQtAct)

    def refresh(self):
        self.panels_layout.refresh()

    def exec_(self, callerWindow=None):
        self.callerWindow = callerWindow
        self.raise_()
        self.qapp.setActiveWindow(self)
        self.showNormal()

    def accept(self):
        self.showMinimized()

    def restart(self):
        restart()
        #os.execlp(sys.executable, 'python', '-m', 'gdesk')

    def showConfig(self):
        dt = DictionaryTreeDialog(config)
        dt.edit()
        config.update(dt.to_dict_list())

    def saveConfig(self):
        path = gui.putfilename('JSON (*.json)', file=config['save_config_file'])
        conf.save_config_json(path)

    def help(self):
        print("Opening %s" % DOC_HTML)
        os.system('start "help" "%s"' % DOC_HTML)

    def about(self):
        aboutScreen = AboutScreen()
        aboutScreen.exec_()

    def license(self):
        message = open(respath / 'LICENSE.txt', 'r').read()
        print(message)
        self.qapp.panels['console'][0].show_me()

    def info(self):
        message = self.qapp.cmdserver.host_info()
        print(message)
        self.qapp.panels['console'][0].show_me()

    def closeEvent(self, event):
        allHidden = True
        for window in self.qapp.windows.values():
            if window.isVisible():
                allHidden = False
                break

        if allHidden:
            event.accept()

        else:
            self.showMinimized()
            self.callerWindow = None
            event.ignore()


class PanelsFloatingPreviews(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.thumbs = []

        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        font = self.font()
        font.setPointSize(font.pointSize() * 2)

        self.caption = QtWidgets.QLabel('Panels')
        self.caption.setFont(font)
        self.caption.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        vbox.addWidget(self.caption)

        self.boxlay = QtWidgets.QGridLayout()
        vbox.addLayout(self.boxlay)

        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)

    @property
    def panels(self):
        return QtWidgets.QApplication.instance().panels

    def preview(self):
        total = sum((len(pans) for cat, pans in self.panels.items()))
        colcount = int((total*16/9)**0.5)

        index = 0
        for cat in self.panels.keys():
            selectedId = self.panels.selected(cat, panel=False)
            for panid in sorted(self.panels[cat].keys()):
                panel = self.panels[cat][panid]
                pixmap = panel.grab().scaled(160, 160, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

                thumb = QtWidgets.QToolButton()
                thumb.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                thumb.setIcon(QtGui.QIcon(pixmap))
                thumb.setIconSize(pixmap.rect().size())
                thumb.setText(panel.short_title)
                if panel.panid == selectedId:
                    thumb.setDown(True)
                thumb.setToolTip(panel.long_title)
                thumb.clicked.connect(CachedArgCall(self.showPanel, panel))

                self.thumbs.append(thumb)

                self.boxlay.addWidget(thumb, index // colcount, index % colcount)

                index += 1

    def showPanel(self, panel):
        for thumb in self.thumbs:
            thumb.setParent(None)
            thumb.hide()

        self.thumbs = []
        self.hide()

        self.selectedPanel = panel

class WindowsFloatingPreviews(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        self.thumbs = []

        self.setLayout(QtWidgets.QVBoxLayout())

        font = self.font()
        font.setPointSize(font.pointSize() * 2)

        self.caption = QtWidgets.QLabel('Windows')
        self.caption.setFont(font)
        self.caption.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        self.layout().addWidget(self.caption)

        self.boxlay = QtWidgets.QGridLayout()
        self.layout().addLayout(self.boxlay)

        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)

    @property
    def windows(self):
        return QtWidgets.QApplication.instance().windows

    def preview(self):
        total = len(self.windows.items())
        colcount = int((total*16/9)**0.5)

        index = 0
        for window in self.windows.values():
            pixmap = window.grab().scaled(160, 160, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

            thumb = QtWidgets.QToolButton()
            thumb.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            thumb.setIcon(QtGui.QIcon(pixmap))
            thumb.setIconSize(pixmap.rect().size())
            #thumb.setText(window.windowTitle())
            thumb.setText(window.name)
            thumb.setToolTip(window.windowTitle())
            thumb.clicked.connect(CachedArgCall(self.showWindow, window))

            self.thumbs.append(thumb)

            self.boxlay.addWidget(thumb, index // colcount, index % colcount)

            index += 1

        #self.show()

    def showWindow(self, window):
        window.showNormal()
        window.raise_()

        for thumb in self.thumbs:
            thumb.hide()

        self.thumbs = []
        self.hide()


class LayoutList(QtWidgets.QListWidget):
    def __init__(self, parent):
        super().__init__(parent=parent)
        self.currentItemChanged.connect(self.changeItem)

    def changeItem(self, item):
        if item is None: return
        layout = config['layout'][item.name]
        text = ''
        ls = LayoutStruct()
        for window in layout["windows"]:
            text += f'window: {window["name"]}\n'
            ls.root = window["docks"]
            text += ls.describe() + '\n\n'
        self.parent().parent().preview.setPlainText(text)


class PanelsLayout(QtWidgets.QWidget):
    def __init__(self, dialog, panels):
        super().__init__(parent=dialog)
        self.dialog = dialog
        self.panels = panels
        self.layout_list = LayoutList(self)
        self.preview = QtWidgets.QPlainTextEdit(self)
        console_font = QtGui.QFont('Consolas', pointSize=config['console']['fontsize'])
        self.preview.setFont(console_font)
        self.preview.setWordWrapMode(QtGui.QTextOption.NoWrap)

        self.vbox = QtWidgets.QVBoxLayout()
        self.setLayout(self.vbox)

        self.box = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.vbox.addWidget(self.box)

        self.box.addWidget(self.layout_list)
        self.box.addWidget(self.preview)

        self.loadBtn = QtWidgets.QPushButton('Load')
        self.loadBtn.clicked.connect(self.loadLayout)

        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.loadBtn)
        self.vbox.addLayout(hbox)
        self.refresh()

    def refresh(self):
        self.layout_list.clear()
        shortcuts = dict((v,k) for k,v in config['shortcuts']['layout'].items())
        for name, layout in config['layout'].items():
            description = layout.get('description', 'no description')
            if shortcuts.get(name, None):
                description += f"\n    [Ctrl+F{shortcuts.get(name, None)}]"
            item = QtWidgets.QListWidgetItem(f'{name}:\n     {description}')
            item.name = name
            self.layout_list.addItem(item)

    def loadLayout(self):
        item = self.layout_list.selectedItems()[0]
        self.panels.restore_state_from_config(item.name)
        self.dialog.accept()

