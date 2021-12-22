"""
Render to qt from agg.
"""
from .. import config

import os
import ctypes
import sys
import threading
import pickle
import logging
import warnings
from distutils.version import LooseVersion

import matplotlib
from matplotlib.transforms import Bbox
from matplotlib.figure import Figure
from matplotlib import cbook
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import FigureCanvasBase, FigureManagerBase
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.backends.backend_qt5 import (
    _BackendQT5, FigureCanvasQT, FigureManagerQT,
    NavigationToolbar2QT, backend_version)
  
from matplotlib.backends.qt_compat import QT_API
from matplotlib.backends.backend_template import FigureCanvasTemplate, FigureManagerTemplate

from .. import gui

if config['qapp']:
    from qtpy import QtCore, QtGui
    from ..panels.matplot import PlotPanel
    
if LooseVersion(matplotlib.__version__) < LooseVersion('3.2'):
    warnings.warn(
        f'Matplotlib version {matplotlib.__version__} not supported.\n'
        f'Version should be 3.2.x, 3.3.x, 3.4.x or 3.5.x')

elif LooseVersion(matplotlib.__version__) < LooseVersion('3.3'):
    setDevicePixelRatio = QtGui.QImage.setDevicePixelRatio
    DEV_PIXEL_RATIO_ATTR = "_dpi_ratio"    
    
elif LooseVersion(matplotlib.__version__) < LooseVersion('3.4'):
    #Version 3.2, 3.3
    from matplotlib.backends.qt_compat import _setDevicePixelRatioF
    setDevicePixelRatio = _setDevicePixelRatioF
    DEV_PIXEL_RATIO_ATTR = "_dpi_ratio"
    
elif LooseVersion(matplotlib.__version__) < LooseVersion('3.5'):
    from matplotlib.backends.qt_compat import _setDevicePixelRatio
    setDevicePixelRatio = _setDevicePixelRatio
    DEV_PIXEL_RATIO_ATTR = "_dpi_ratio"
    
elif LooseVersion(matplotlib.__version__) >= LooseVersion('3.5'):
    from matplotlib.backends.qt_compat import _setDevicePixelRatio
    setDevicePixelRatio = _setDevicePixelRatio
    DEV_PIXEL_RATIO_ATTR = "_device_pixel_ratio"   

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", "Starting a Matplotlib GUI outside of the main thread will likely fail.")

def draw_if_interactive():
    """
    For image backends - is not required.
    For GUI backends - this should be overridden if drawing should be done in
    interactive python mode.
    """  
    if matplotlib.is_interactive(): 
        show()

def show(*, block=None):
    """
    For image backends - is not required.
    For GUI backends - show() is usually the last line of a pyplot script and
    tells the backend that it is time to draw.  In interactive mode, this
    should do nothing.
    """ 
    #manager = Gcf.get_active()    
    for manager in Gcf.get_all_fig_managers():
        manager.show()
        
def new_figure_manager(num, *args, FigureClass=Figure, **kwargs):
    """Create a new figure manager instance."""
    # If a main-level app must be created, this (and
    # new_figure_manager_given_figure) is the usual place to do it -- see
    # backend_wx, backend_wxagg and backend_tkagg for examples.  Not all GUIs
    # require explicit instantiation of a main-level app (e.g., backend_gtk3)
    # for pylab.
    thisFig = FigureClass(*args, **kwargs)
    return new_figure_manager_given_figure(num, thisFig)

def new_figure_manager_given_figure(num, figure):
    """Create a new figure manager instance for the given figure."""
    
    #print(f'timer: {time.perf_counter()}')

    if not gui.valid() or gui._qapp is None:                    
        #In case of comming from other Process
        #Don't do a guicall, FigureCanvasGh2 or FigureManagerQT is not pickable!
        #Is called if figure, line, ... is depickled from the interprocess queue
        canvas = FigureCanvasBase(figure)
        manager = FigureManagerGh2Child(canvas, num)
        
    else:
        canvas = gui.gui_call(FigureCanvasGh2, figure)    
        manager = FigureManagerGh2(canvas, num)
        
    return manager        


class FigureCanvasGh2(FigureCanvasAgg, FigureCanvasQT):

    def __init__(self, figure):
        # Must pass 'figure' as kwarg to Qt base class.
        super().__init__(figure=figure)        
            
        
    @property
    def dev_pixel_ratio(self):
        return getattr(self, DEV_PIXEL_RATIO_ATTR)

    def paintEvent(self, event):
        """
        Copy the image from the Agg canvas to the qt.drawable.

        In Qt, all drawing should be done inside of here when a widget is
        shown onscreen.
        """
        logger.debug('calling paintEvent')
        
        if matplotlib.__version__[:3] in ['3.2', '3.3']:
            if self._update_dpi():
                # The dpi update triggered its own paintEvent.
                return
                
        self._draw_idle()  # Only does something if a draw is pending.

        # If the canvas does not have a renderer, then give up and wait for
        # FigureCanvasAgg.draw(self) to be called.
        if not hasattr(self, 'renderer'):
            return

        painter = QtGui.QPainter(self)
        try:
            # See documentation of QRect: bottom() and right() are off
            # by 1, so use left() + width() and top() + height().
            rect = event.rect()
            # scale rect dimensions using the screen dpi ratio to get
            # correct values for the Figure coordinates (rather than
            # QT5's coords)
            width = rect.width() * self.dev_pixel_ratio
            height = rect.height() * self.dev_pixel_ratio
            left, top = self.mouseEventCoords(rect.topLeft())
            # shift the "top" by the height of the image to get the
            # correct corner for our coordinate system
            bottom = top - height
            # same with the right side of the image
            right = left + width
            # create a buffer using the image bounding box
            bbox = Bbox([[left, bottom], [right, top]])
            reg = self.copy_from_bbox(bbox)
            buf = cbook._unmultiplied_rgba8888_to_premultiplied_argb32(
                memoryview(reg))

            # clear the widget canvas
            painter.eraseRect(rect)

            qimage = QtGui.QImage(buf, buf.shape[1], buf.shape[0],
                                  QtGui.QImage.Format_ARGB32_Premultiplied)
            setDevicePixelRatio(qimage, self.dev_pixel_ratio)
            # set origin using original QT coordinates
            origin = QtCore.QPoint(rect.left(), rect.top())
            painter.drawImage(origin, qimage)
            # Adjust the buf reference count to work around a memory
            # leak bug in QImage under PySide on Python 3.
            if QT_API in ('PySide', 'PySide2'):
                ctypes.c_long.from_address(id(buf)).value = 1

            self._draw_rect_callback(painter)
        finally:
            painter.end()
            
    def draw_idle(self):
        logger.debug('calling draw_idle')
        gui.gui_call(FigureCanvasQT.draw_idle, self) 
        
    def destroy(self, *args):
        gui.gui_call(FigureCanvasQT.destroy, self, *args)                                    

    def blit(self, bbox=None):
        # docstring inherited
        # If bbox is None, blit the entire canvas. Otherwise
        # blit only the area defined by the bbox.
        if bbox is None and self.figure:
            bbox = self.figure.bbox

        # repaint uses logical pixels, not physical pixels like the renderer.
        l, b, w, h = [int(pt / self._dpi_ratio) for pt in bbox.bounds]
        t = b + h
        self.repaint(l, self.renderer.height / self._dpi_ratio - t, w, h)

    def print_figure(self, *args, **kwargs):
        super().print_figure(*args, **kwargs)
        self.draw()
        
class FigureManagerGh2(FigureManagerBase):

    """
    Wrap everything up into a window for the pylab interface

    For non interactive backends, the base class does all the work
    """       
    def __init__(self, canvas, num):
        super().__init__(canvas, num)
        #self.panel = gui.gui_call(gui._qapp.panels.new_panel, PlotPanel, 'main', num, None, args=(canvas,))
        
        def make_and_hide_plot_panel(PanelClass, parentName=None, panid=None, floating=False, position=None, size=None, args=(), kwargs={}):
            panel = gui._qapp.panels.new_panel(PanelClass, parentName, panid, floating, position, size, args, kwargs)
            panel.window().hide()
            return panel
            
        self.panel = gui.gui_call(make_and_hide_plot_panel, PlotPanel, 'main', num, None, args=(canvas,))
    
    def show(self):
        """
        For GUI backends, show the figure window and redraw.
        For non-GUI backends, raise an exception to be caught
        by :meth:`~matplotlib.figure.Figure.show`, for an
        optional warning.
        """
        if gui.valid():            
            gui.gui_call(PlotPanel.show_me, self.panel)
            gui.gui_call(PlotPanel.refresh, self.panel)
        else:        
            raise ValueError(f'gui called from unknown thread {os.getpid()}/{threading.current_thread()}')
        
    def destroy(self, *args):        
        if 'plot' in gui._qapp.panels.keys():        
            gui.gui_call(PlotPanel.close_panel, self.panel)
        else:
            pass
            
class FigureManagerGh2Child(FigureManagerBase):

    """
    Wrap everything up into a window for the pylab interface

    For non interactive backends, the base class does all the work
    """       
    def __init__(self, canvas, num):
        super().__init__(canvas, num)
        self.panel = None
    
    def show(self):
        """
        For GUI backends, show the figure window and redraw.
        For non-GUI backends, raise an exception to be caught
        by :meth:`~matplotlib.figure.Figure.show`, for an
        optional warning.
        """
        if gui.valid():            
            gui.plot.show(self.canvas.figure)
        else:        
            raise ValueError(f'gui called from unknown thread {os.getpid()}/{threading.current_thread()}')
              
        

FigureCanvas = FigureCanvasGh2
FigureManager = FigureManagerGh2
