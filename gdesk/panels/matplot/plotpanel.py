import sys
import time
import logging
import pickle
from pathlib import Path

from matplotlib.backends.backend_qt5agg import  FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib._pylab_helpers import Gcf
from matplotlib.backends.backend_template import FigureCanvasTemplate, FigureManagerTemplate 
import pylab

from qtpy import QtWidgets, QtCore, QtGui              

from ... import gui, config
from .. import BasePanel, CheckMenu

respath = Path(config['respath'])
logger = logging.getLogger(__name__)

set_active_backup = Gcf.set_active

def gcf_set_active(manager):
    # Note that this function is called by pyplot
    # - when the user clicks on the canvas (callback needed on canvas object?)
    # - on pyplot.figure(number)
    if pylab.get_backend() == config.get("matplotlib", {}).get("backend", None):
        gui.plot.select(manager.num)
    else:
        set_active_backup(manager)

#Hacking pyplot !
Gcf.set_active = gcf_set_active

def restore_gcf_set_active():
    Gcf.set_active = set_active_backup
           
class PlotPanel(BasePanel):
    panelCategory = 'plot'
    panelShortName = 'basic'
    userVisible = True 
    
    classIconFile = str(respath / 'icons' / 'px16' / 'chart_curve.png')
    
    def __init__(self, parent=None, pid=None, figure_or_canvas=None):
        super().__init__(parent, pid, 'plot')
        
        self.fileMenu = self.menuBar().addMenu("&File")        
        self.addMenuItem(self.fileMenu, 'Open...' , self.openFigure)
        self.addMenuItem(self.fileMenu, 'Save As...' , self.saveFigure)
        self.addMenuItem(self.fileMenu, 'Close' , self.close_me_from_menu, icon = 'cross.png')
        
        self.viewMenu = CheckMenu("&View", self.menuBar())
        self.menuBar().addMenu(self.viewMenu)
        
        self.addMenuItem(self.viewMenu, 'Refresh', self.refresh,
            statusTip = "Refresh the plot",
            icon = 'update.png')
        self.addMenuItem(self.viewMenu, 'Grid', self.grid,
            statusTip = "Show/hide grid",
            icon = 'layer_grid.png')
        self.addMenuItem(self.viewMenu, 'Tight', self.tight)        
        self.addMenuItem(self.viewMenu, 'Interactive', self.toggle_interactive,
            checkcall=lambda: pylab.isinteractive())
        
        self.addBaseMenu()        
        
        if hasattr(figure_or_canvas, 'canvas'):
            self.figure = figure_or_canvas
            self.canvas = figure_or_canvas.canvas            
        else:
            self.figure = figure_or_canvas.figure
            self.canvas = figure_or_canvas                  
        
        self.setCentralWidget(self.canvas)         
        
        self.nav = NavigationToolbar(self.canvas, self)
        self.nav.setIconSize(QtCore.QSize(24,24))
        self.addToolBar(self.nav)        
        self.statusBar().hide()
        #self.statusBar().addWidget(self.nav)
        
    def showNewFigure(self, figure):
        from ghawk2.matplotbe import FigureCanvasGh2
        
        mgr = self.canvas.manager
        self.figure = figure
        self.canvas = FigureCanvasGh2(figure)
        self.canvas.manager = mgr
        mgr.canvas = self.canvas
        
        self.setCentralWidget(self.canvas)
        
        self.statusBar().removeWidget(self.nav)
        
        self.nav = NavigationToolbar(self.canvas, self)
        self.nav.setIconSize(QtCore.QSize(24,24))        
        
        #self.statusBar().addWidget(self.nav)
        self.addToolBar(self.nav) 
        
        self.canvas.draw_idle()   

    def openFigure(self):
        import pickle
        
        filter = "Pickle (*.pkl)"
        
        filepath, selectedFilter = gui.getfile(filter=filter, title='Open Figure')

        if filepath == '':
            return        
            
        pickle.load(open(filepath, 'rb'))

    def saveFigure(self):
        figure = self.figure

        filter = "Portable Network Graphics (*.png)"
        filter += ";;Scalable Vector Graphics (*.svg)"
        filter += ";;Pickle (*.pkl)"
        
        filepath, selectedFilter = gui.putfile(filter=filter, title='Save Figure as', defaultfilter="Scalable Vector Graphics (*.svg)")
        
        if filepath == '':
            return                
        
        if selectedFilter == "Pickle (*.pkl)":
            import pickle
            with open(filepath, 'wb') as fp:
                pickle.dump(figure, fp)
        else:
            plt = gui.prepareplot()
            plt.savefig(filepath)
        
    def grid(self):
        f = self.figure
        for axe in f.axes:
            axe.grid()
            
        self.canvas.draw_idle()
        
    def tight(self):
        self.figure.tight_layout()
        self.canvas.draw_idle()
        
    def toggle_interactive(self):
        pylab.interactive(not pylab.isinteractive())
        
    def refresh(self):
        self.canvas.draw_idle()
                
    def select(self):      
        manager = self.canvas.manager
        set_active_backup(manager)
        super().select()
        
    def close_me_from_menu(self):  
        #Use the matplotlib backend to close
        pylab.close(self.panid)
        
    def close_panel(self):              
        #Called from the matplotlib backend
        super().close_panel()

      
        
        