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
    
from .blueprint import make_thumbnail    

class OperationMenu(CheckMenu):

    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)                   

        basePanel.addMenuItem(self, 'Sum', self.sum,
            statusTip="Sum of 2 images", icon='image_add')             
        basePanel.addMenuItem(self, 'Subtraction', self.subtraction,
            statusTip="Subtraction of 2 images", icon='image_delete')              
        basePanel.addMenuItem(self, 'Difference', self.difference,
            statusTip="Difference of 2 images")   
        basePanel.addMenuItem(self, 'Multiply', self.multiply,
            statusTip="Multiply of 2 images")             

    def sum(self):
        imviewers = dict()
        
        for imviewid in sorted(gui.qapp.panels['image'].keys()):
            imviewers[f'image#{imviewid}'] =  imviewid
            
        imviewidkeys = list(imviewers.keys())
        form = [
            ("Image 1", [1] + imviewidkeys),
            ("Image 2", [2] + imviewidkeys)]
            
        results = fedit(form, title='Sum')        
        
        if results is None: return
        image1_ind, image2_ind = results
        image1_id  = imviewers[imviewidkeys[image1_ind-1]]
        image2_id  = imviewers[imviewidkeys[image2_ind-1]]
            
        def console_run(image1_pid, image2_pid):
            gui.img.select(image1_pid)
            image1 = gui.vs
            gui.img.select(image2_pid)
            image2 = gui.vs
            
            dtype1 = image1.dtype 
            dtype2 = image2.dtype            

            if dtype1 == dtype2 == 'uint8':            
                image3 = image1.astype('uint16') + image2.astype('uint16')
                
            elif dtype1 == dtype2 == 'uint16':            
                image3 = image1.astype('uint32') + image2.astype('uint32')
                
            else:
                image3 = image1.astype('double') + image2.astype('double')
            
            pid = gui.img.new()
            gui.img.select(pid)
            gui.img.show(image3)
        
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run, args=(image1_id, image2_id))
        
    def subtraction(self):
        imviewers = dict()
        
        for imviewid in sorted(gui.qapp.panels['image'].keys()):
            imviewers[f'image#{imviewid}'] =  imviewid
            
        imviewidkeys = list(imviewers.keys())
        form = [
            ("Offset", 0),
            ("Image 1", [1] + imviewidkeys),
            ("Image 2", [2] + imviewidkeys)]
            
        results = fedit(form, title='Subtraction')        
        
        if results is None: return
        offset, image1_ind, image2_ind = results
        image1_id  = imviewers[imviewidkeys[image1_ind-1]]
        image2_id  = imviewers[imviewidkeys[image2_ind-1]]
            
        def console_run(image1_pid, image2_pid, offset):
            gui.img.select(image1_pid)
            image1 = gui.vs
            gui.img.select(image2_pid)
            image2 = gui.vs           
            
            dtype1 = image1.dtype 
            dtype2 = image2.dtype 
            
            if dtype1 == dtype2 == 'uint8':
                image3 = (image1.astype('int16') - image2.astype('int16') + offset)
                
            elif dtype1 == dtype2 == 'uint16':
                image3 = (image1.astype('int32') - image2.astype('int32') + offset)
                
            else:
                image3 = image1.astype('double') - image2.astype('double') + offset
            
            pid = gui.img.new()
            gui.img.select(pid)
            gui.img.show(image3)                  
        
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run, args=(image1_id, image2_id, offset))           

    def difference(self):
        imviewers = dict()
        
        for imviewid in sorted(gui.qapp.panels['image'].keys()):
            imviewers[f'image#{imviewid}'] =  imviewid
            
        imviewidkeys = list(imviewers.keys())
        form = [
            ("Image 1", [1] + imviewidkeys),
            ("Image 2", [2] + imviewidkeys)]
            
        results = fedit(form, title='Difference')        
        
        if results is None: return
        image1_ind, image2_ind = results
        image1_id  = imviewers[imviewidkeys[image1_ind-1]]
        image2_id  = imviewers[imviewidkeys[image2_ind-1]]
            
        def console_run(image1_pid, image2_pid):
            gui.img.select(image1_pid)
            image1 = gui.vs
            gui.img.select(image2_pid)
            image2 = gui.vs
            
            dtype1 = image1.dtype 
            dtype2 = image2.dtype            

            if dtype1 == dtype2 == 'uint8':
                image3 = np.abs(image1.astype('int16') - image2.astype('int16')).clip(0, 2**8-1).astype('uint8')
                
            elif dtype1 == dtype2 == 'uint16':
                image3 = np.abs(image1.astype('int32') - image2.astype('int32')).clip(0, 2**16-1).astype('uint16')
                
            else:
                image3 = np.abs(image1.astype('double') - image2.astype('double'))
            
            pid = gui.img.new()
            gui.img.select(pid)
            gui.img.show(image3)                  
        
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run, args=(image1_id, image2_id))        

    def multiply(self):
        imviewers = dict()
        
        for imviewid in sorted(gui.qapp.panels['image'].keys()):
            imviewers[f'image#{imviewid}'] =  imviewid
            
        imviewidkeys = list(imviewers.keys())
        form = [
            ("Image 1", [1] + imviewidkeys),
            ("Image 2", [2] + imviewidkeys)]
            
        results = fedit(form, title='Multiply')        
        
        if results is None: return
        image1_ind, image2_ind = results
        image1_id  = imviewers[imviewidkeys[image1_ind-1]]
        image2_id  = imviewers[imviewidkeys[image2_ind-1]]
            
        def console_run(image1_pid, image2_pid):
            gui.img.select(image1_pid)
            image1 = gui.vs
            gui.img.select(image2_pid)
            image2 = gui.vs
            
            dtype1 = image1.dtype 
            dtype2 = image2.dtype             

            if dtype1 == dtype2 == 'uint8':
                image3 = image1.astype('uint16') * image2.astype('uint16')
                
            elif dtype1 == dtype2 == 'uint16':
                image3 = image1.astype('uint32') * image2.astype('uint32')
            
            pid = gui.img.new()
            gui.img.select(pid)
            gui.img.show(image3)                  
        
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run, args=(image1_id, image2_id))          