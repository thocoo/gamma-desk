import os
import time
import collections
from pathlib import Path
import types
from collections.abc import Iterable
import queue
import logging

import numpy as np

logger = logging.getLogger(__name__)

from ... import config, gui

if config.get('qapp', False):
    #only import qt stuff if process is gui
    from ...panels import CheckMenu    
    from ...dialogs.formlayout import fedit
    
else:
    #fake it
    CheckMenu = object
    # The nested functions are still callable
    # from a non qt process

import cv2

class OpenCvMenu(CheckMenu):

    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)

        #Process
        basePanel.addMenuItem(self, 'Resize', self.image_resize,
            statusTip="Resize the image", icon = 'resize_picture.png')
        basePanel.addMenuItem(self, 'Box Blur', self.box_blur,
            statusTip="Blur the image using a box sized kernel", icon = 'blur.png')       
        basePanel.addMenuItem(self, 'Gaussian Blur', self.gaussian_blur,
            statusTip="Blur using guassian kernel", icon = 'blur.png')                
        basePanel.addMenuItem(self, 'Median Blur', self.median_blur,
            statusTip="Blur using median filter", icon = 'blur.png')               

    def image_resize(self):
        interpoloptions = {
            "Nearest": cv2.INTER_NEAREST,
            "Linear": cv2.INTER_LINEAR,            
            "Cubic": cv2.INTER_CUBIC,
            "Lanczos4": cv2.INTER_LANCZOS4,
            "Area": cv2.INTER_AREA}
            
        shape = gui.vs.shape[:2]
        interpolkeys = list(interpoloptions.keys())                
        form = [("width", shape[1]), ("height", shape[0]), ("interpolation", [5] + interpolkeys)]
        results = fedit(form)
        if results is None: return
        width, height, interpolind = results
        interpol = interpoloptions[interpolkeys[interpolind-1]]
        
        def console_run(width, height, interpol):
            array = cv2.resize(gui.vs, (width, height), interpolation=interpol)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(width, height, interpol))
        
    def box_blur(self):
        form = [("Kernel Size", 15)]
        results = fedit(form)
        if results is None: return
        ksize = results[0]
        
        def console_run(ksize):
            array = cv2.blur(gui.vs, ksize=(ksize, ksize))
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ksize,))
        
    def gaussian_blur(self):
        form = [("Kernel Size", 15)]
        results = fedit(form)
        if results is None: return
        ksize = results[0]
        
        def console_run(ksize):
            array = cv2.GaussianBlur(gui.vs, ksize=(ksize, ksize), sigmaX=0)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ksize,))
        
    def median_blur(self):
        form = [("Kernel Size", 15)]
        results = fedit(form)
        if results is None: return
        ksize = results[0]
        
        def console_run(ksize):
            array = cv2.medianBlur(gui.vs, ksize=ksize)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ksize,))           
        

