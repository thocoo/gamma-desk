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
        basePanel.addMenuItem(self, 'Bilateral Filter', self.bilateral,
            statusTip="Apply Bilateral Filter")        
        basePanel.addMenuItem(self, 'Laplacian', self.laplacian,
            statusTip="Calculates the Laplacian")             
        basePanel.addMenuItem(self, 'Box Filter', self.box,
            statusTip="The sum of the pixel values overlapping the filter")               
        basePanel.addMenuItem(self, 'Square Box Filter', self.sqrbox,
            statusTip="The sum of squares of the pixel values overlapping the filter")             
        basePanel.addMenuItem(self, 'Demosaic', self.demosaic,
            statusTip="Demosaicing using bilinear interpolation", icon='things_digital.png')              

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
        results = fedit(form, title='Resize')
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
        results = fedit(form, title='Box Blur')
        if results is None: return
        ksize = results[0]
        
        def console_run(ksize):
            array = cv2.blur(gui.vs, ksize=(ksize, ksize))
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ksize,))
        
    def gaussian_blur(self):
        form = [("Kernel Size", 15)]
        results = fedit(form, title='Guassian Blur')
        if results is None: return
        ksize = results[0]
        
        def console_run(ksize):
            array = cv2.GaussianBlur(gui.vs, ksize=(ksize, ksize), sigmaX=0)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ksize,))
        
    def median_blur(self):
        form = [("Kernel Size", 15)]
        results = fedit(form, title='Median Blur')
        if results is None: return
        ksize = results[0]
        
        def console_run(ksize):
            array = cv2.medianBlur(gui.vs, ksize=ksize)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ksize,))  
        
    def bilateral(self):
        borders = {
            'Reflect 101': cv2.BORDER_REFLECT_101,
            'Constant': cv2.BORDER_CONSTANT,
            'Replicate': cv2.BORDER_REPLICATE,
            'Reflect': cv2.BORDER_REFLECT,
            'Wrap': cv2.BORDER_WRAP,
            'Transparant': cv2.BORDER_TRANSPARENT,            
            'Isolated': cv2.BORDER_ISOLATED}
            
        border_keys = list(borders.keys())
            
        form = [
            ("Diameter", 10),
            ("Sigma Color", 10.0),
            ("Sigma Space", 10.0),
            ("Border", [1] + border_keys)]
            
        results = fedit(form, title='Bilateral Filter')
        
        if results is None: return
        d, sigma_color, sigma_space, border_index = results
        border = borders[border_keys[border_index - 1]]
        
        def console_run(d, sigma_color, sigma_space, border):
            array = cv2.bilateralFilter(gui.vs, d, sigma_color, sigma_space, border)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(d, sigma_color, sigma_space, border)) 
                
    def laplacian(self):
        borders = {
            'Reflect 101': cv2.BORDER_REFLECT_101,
            'Constant': cv2.BORDER_CONSTANT,
            'Replicate': cv2.BORDER_REPLICATE,
            'Reflect': cv2.BORDER_REFLECT,
            'Transparant': cv2.BORDER_TRANSPARENT,            
            'Isolated': cv2.BORDER_ISOLATED}
            
        border_keys = list(borders.keys())
            
        form = [
            ("Desired Depth", 5),
            ("Aperture Size", 1),
            ("Scale", 1.0),
            ("Delta", 1.0),
            ("Border", [1] + border_keys)]
            
        results = fedit(form, title='Laplacian')
        
        if results is None: return
        ddepth, ksize, scale, delta, border_index = results
        border = borders[border_keys[border_index - 1]]
        
        def console_run(ddepth, ksize, scale, delta, border):
            array = cv2.Laplacian(gui.vs, ddepth, ksize=ksize, scale=scale, delta=delta, borderType=border)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ddepth, ksize, scale, delta, border))         
        
    def box(self):
        borders = {
            'Reflect 101': cv2.BORDER_REFLECT_101,
            'Constant': cv2.BORDER_CONSTANT,
            'Replicate': cv2.BORDER_REPLICATE,
            'Reflect': cv2.BORDER_REFLECT,
            'Transparant': cv2.BORDER_TRANSPARENT,            
            'Isolated': cv2.BORDER_ISOLATED}
            
        border_keys = list(borders.keys())
            
        form = [
            ("Depth", -1),
            ("Kernel Size", 5),
            ("Normalize", False),
            ("Border", [1] + border_keys)]
            
        results = fedit(form, title='Box Filter')
        
        if results is None: return
        ddepth, ksize, normalize, border_index = results
        border = borders[border_keys[border_index - 1]]
        
        def console_run(ddepth, ksize, normalize, border):
            array = cv2.boxFilter(gui.vs, ddepth=ddepth, ksize=(ksize, ksize), normalize=normalize, borderType=border)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ddepth, ksize, normalize, border))          
                
    def sqrbox(self):
        borders = {
            'Reflect 101': cv2.BORDER_REFLECT_101,
            'Constant': cv2.BORDER_CONSTANT,
            'Replicate': cv2.BORDER_REPLICATE,
            'Reflect': cv2.BORDER_REFLECT,
            'Transparant': cv2.BORDER_TRANSPARENT,            
            'Isolated': cv2.BORDER_ISOLATED}
            
        border_keys = list(borders.keys())
            
        form = [
            ("Depth", -1),
            ("Kernel Size", 5),
            ("Normalize", False),
            ("Border", [1] + border_keys)]
            
        results = fedit(form, title='Square Box Filter')
        
        if results is None: return
        ddepth, ksize, normalize, border_index = results
        border = borders[border_keys[border_index - 1]]
        
        def console_run(ddepth, ksize, normalize, border):
            array = cv2.sqrBoxFilter(gui.vs, ddepth=ddepth, ksize=(ksize, ksize), normalize=normalize, borderType=border)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(ddepth, ksize, normalize, border))         

    def demosaic(self):
        bayerconfigs = {
            "BG": cv2.COLOR_BayerBG2BGR,
            "GB": cv2.COLOR_BayerGB2BGR,            
            "RG": cv2.COLOR_BayerRG2BGR,
            "GR": cv2.COLOR_BayerGR2BGR}
            
        bayerconfigkeys = list(bayerconfigs.keys())
            
        form = [("Bayer Config", [1] + bayerconfigkeys)]
        results = fedit(form, title='Demosaic')
        if results is None: return
        bayerconfigind = results[0]
        bayerconfig = bayerconfigs[bayerconfigkeys[bayerconfigind-1]]
        
        def console_run(bayerconfig):
            array = cv2.demosaicing(gui.vs, code=bayerconfig)
            gui.show(array)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run,  args=(bayerconfig,))        
        

