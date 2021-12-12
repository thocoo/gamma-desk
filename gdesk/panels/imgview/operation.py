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
        basePanel.addMenuItem(self, 'Difference', self.difference,
            statusTip="Difference of 2 images", icon='image_delete')   

    def sum(self):
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

            image3 = (image1.astype('int32') + image2.astype('int32')).clip(0, 2**16-1).astype('uint16')
            
            pid = gui.img.new()
            gui.img.select(pid)
            gui.img.show(image3)
        
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run, args=(image1_id, image2_id))

    def difference(self):
        imviewers = dict()
        
        for imviewid in sorted(gui.qapp.panels['image'].keys()):
            imviewers[f'image#{imviewid}'] =  imviewid
            
        imviewidkeys = list(imviewers.keys())
        form = [
            ("Offset", 0),
            ("Image 1", [1] + imviewidkeys),
            ("Image 2", [2] + imviewidkeys)]
            
        results = fedit(form, title='Difference')        
        
        if results is None: return
        offset, image1_ind, image2_ind = results
        image1_id  = imviewers[imviewidkeys[image1_ind-1]]
        image2_id  = imviewers[imviewidkeys[image2_ind-1]]
            
        def console_run(image1_pid, image2_pid, offset):
            gui.img.select(image1_pid)
            image1 = gui.vs
            gui.img.select(image2_pid)
            image2 = gui.vs           

            image3 = (image1.astype('int32') - image2.astype('int32') + offset).clip(-2**15, 2**15-1).astype('int16')
            
            pid = gui.img.new()
            gui.img.select(pid)
            gui.img.show(image3)                  
        
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(console_run, args=(image1_id, image2_id, offset))           