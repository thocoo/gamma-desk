import logging
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np

try:
    import scipy
    import scipy.ndimage
    HAS_SCIPY = True

except:
    HAS_SCIPY = False

from qtpy import QtCore, QtGui
from qtpy.QtWidgets import QAction, QMenu

from ...panels import CheckMenu
from ...gcore.utils import ActionArguments
from ...dialogs.formlayout import fedit
from ...utils import imconvert
from .regoi import RoiConfigDialog

from ... import config, gui

RESPATH = Path(config['respath'])


class EditMenu(CheckMenu):
    
    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)    
        
        self.basePanel = basePanel                 
            
        basePanel.addMenuItem(self, 'Show Prior Image', self.piorImage,
            enablecall = lambda: self.imviewer.imgdata.imghist.prior_length() > 0,
            statusTip="Get the prior image from the history stack and show it",
            icon = 'undo.png')
            
        basePanel.addMenuItem(self, 'Show Next Image', self.nextImage,
            enablecall = lambda: self.imviewer.imgdata.imghist.next_length() > 0,
            statusTip="Get the next image from the history stack and show it",
            icon = 'redo.png')

        self.addSeparator()

        basePanel.addMenuItem(self, 'Copy Scaled Selection', self.placeViewerOnClipboard,
            icon = str(RESPATH / 'icons' / 'px16' /'resize_picture.png'))
            
        basePanel.addMenuItem(self, 'Copy 100% Zoom', self.placeQimgOnClipboard,
            statusTip="Place the 8bit image on clipboard, offset and gain applied",
            icon = str(RESPATH / 'icons' / 'px16' / 'two_pictures.png'))            
            
        basePanel.addMenuItem(self, 'Paste', self.showFromClipboard,
            statusTip="Paste content of clipboard in this image viewer",
            icon = 'picture_clipboard.png')
            
        basePanel.addMenuItem(self, 'Grab Desktop', self.grabDesktop,
            icon = 'lcd_tv_image.png')
     

    @property
    def imviewer(self):
        return self.basePanel.imviewer
        
        
    @property
    def ndarray(self):
        return self.basePanel.ndarray        
        
    
    @property    
    def imgprof(self):
        return self.basePanel.imgprof
        
        
    def show_array(self, image, log=False):
        self.basePanel.show_array(image, log=log)
        
        
    def refresh(self):
        self.imviewer.refresh()        
        
        
    def piorImage(self):
        if self.imviewer.imgdata.imghist.prior_length() > 0:
            arr = self.imviewer.imgdata.imghist.prior(self.ndarray)
            self.show_array(arr, log=False)
            

    def nextImage(self):
        if self.imviewer.imgdata.imghist.next_length() > 0:
            arr = self.imviewer.imgdata.imghist.next(self.ndarray)
            self.show_array(arr, log=False)  
        
        
    def placeViewerOnClipboard(self):
        qimg, props = self.basePanel.getViewerQImage()        
        clipboard = gui.qapp.clipboard()
        clipboard.setImage(qimg.copy())      


    def placeQimgOnClipboard(self):
        clipboard = gui.qapp.clipboard()
        #If qimg is not copied, GH crashes on paste after the qimg instance has been garbaged!
        #Clipboard can only take ownership if the object is a local?
        qimg = self.imviewer.imgdata.qimg.copy()
        clipboard.setImage(qimg)   


    def showFromClipboard(self):
        arr = gui.get_clipboard_image()
        self.show_array(arr)  


    def grabDesktop(self):       
        screens = gui.qapp.screens()    
        screen_names = [1] + [sc.name() for sc in screens]
        form = [
            ('Screen', screen_names),
            ('Delay', 1.0)]
        
        results = fedit(form, title='Screenshot')
        
        if results is None: return
        
        screen_index, delay = results
        screen_name = screen_names[screen_index]
        
        screen = [sc for sc in screens if sc.name() == screen_name][0]        
        
        def screenGrab():
            pixmap = screen.grabWindow(0)
            
            qimage = pixmap.toImage()
            arr = imconvert.qimage_to_ndarray(qimage)
            self.show_array(arr)
        
        QtCore.QTimer.singleShot(delay * 1000, screenGrab)         
