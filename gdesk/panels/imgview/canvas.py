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

from ...panels import CheckMenu
from ...gcore.utils import ActionArguments
from ...utils import clip_array
from ...utils import imconvert

from ... import config, gui

respath = Path(config['respath'])


class CanvasMenu(CheckMenu):

    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)
        
        self.basePanel = basePanel            

        basePanel.addMenuItem(self, 'Flip Horizontal', self.flipHorizontal,
            statusTip="Flip the image Horizontal",
            icon = str(respath / 'icons' / 'px16' / 'shape_flip_horizontal.png'))
            
        basePanel.addMenuItem(self, 'Flip Vertical'  , self.flipVertical,
            statusTip="Flip the image Vertical",
            icon = str(respath / 'icons' / 'px16' / 'shape_flip_vertical.png'))
            
        basePanel.addMenuItem(self, 'Rotate Left 90' , self.rotate90,
            statusTip="Rotate the image 90 degree anti clockwise",
            icon = str(respath / 'icons' / 'px16' / 'shape_rotate_anticlockwise.png'))
            
        basePanel.addMenuItem(self, 'Rotate Right 90', self.rotate270,
            statusTip="Rotate the image 90 degree clockwise",
            icon = str(respath / 'icons' / 'px16' / 'shape_rotate_clockwise.png'))
            
        basePanel.addMenuItem(self, 'Rotate 180'     , self.rotate180,
            statusTip="Rotate the image 180 degree")
            
        basePanel.addMenuItem(self, 'Rotate any Angle...', triggered=self.rotateAny, enabled=HAS_SCIPY,
            statusTip="Rotate any angle")
            
        basePanel.addMenuItem(self, 'Crop on Selection', self.crop,
            statusTip="Crop the image on the current rectangle selection",
            icon = str(respath / 'icons' / 'px16' / 'transform_crop.png'))
            
        basePanel.addMenuItem(self, 'Resize Canvas...', self.canvasResize,
            statusTip="Add or remove borders",
            icon = str(respath / 'icons' / 'px16' / 'canvas_size.png'))
            
        basePanel.addMenuItem(self, 'Resize Image', triggered=self.resize, enabled=HAS_SCIPY,
            statusTip="Resize the image by resampling",
            icon = str(respath / 'icons' / 'px16' / 'scale_image.png'))
            
    @property
    def ndarray(self):
        return self.basePanel.ndarray
                       
        
    def show_array(self, array):
        self.basePanel.show_array(array)           
        

    def flipHorizontal(self):
        self.show_array(self.ndarray[:, ::-1])


    def flipVertical(self):
        self.show_array(self.ndarray[::-1, :])


    def rotate90(self):
        rotated = np.rot90(self.ndarray, 1).copy()
        self.show_array(rotated)


    def rotate180(self):
        self.show_array(self.ndarray[::-1, ::-1])


    def rotate270(self):
        rotated = np.rot90(self.ndarray, 3).copy()
        self.show_array(rotated)


    def rotateAny(self):
        with ActionArguments(self) as args:
            args['angle'] = 0.0

        if args.isNotSet():
            form = [('Angle', args['angle'])]
            results = gui.fedit(form, title='Rotate')
            if results is None: return
            args['angle'] = results[0]

        with gui.qapp.waitCursor(f'Rotating {args["angle"]} degree'):
            procarr = scipy.ndimage.rotate(self.ndarray, args['angle'], reshape=True)
            self.show_array(procarr)


    def crop(self):
        self.basePanel.select()
        croped_array = gui.vr.copy()
        gui.img.show(croped_array)
        self.basePanel.selectNone()


    def canvasResize(self):
        old_height, old_width = self.ndarray.shape[:2]

        with ActionArguments(self) as args:
            args['width'], args['height'] = old_width, old_height

        channels = self.ndarray.shape[2] if self.ndarray.ndim == 3 else 1

        if args.isNotSet():

            form = [('Width', args['width']), ('Height', args['height'])]
            results = gui.fedit(form, title='Canvas Resize')
            if results is None: return
            args['width'], args['height'] = results

        new_width = args['width']
        new_height = args['height']

        if channels == 1:
            procarr = np.ndarray((new_height, new_width), dtype=self.ndarray.dtype)
        else:
            procarr = np.ndarray((new_height, new_width, channels), dtype=self.ndarray.dtype)

        #What with the alpha channel?
        procarr[:] = 0

        width = min(old_width, new_width)
        height = min(old_height, new_height)
        ofow = (old_width - width) // 2
        ofnw = (new_width - width) // 2
        ofoh = (old_height - height) // 2
        ofnh = (new_height - height) // 2
        procarr[ofnh:ofnh+height, ofnw:ofnw+width, ...] = self.ndarray[ofoh:ofoh+height, ofow:ofow+width, ...]
        self.show_array(procarr)


    def resize(self):
        source = self.ndarray
        shape = self.ndarray.shape

        form = [("width", shape[1]), ("height", shape[0]), ("order", 1)]
        results = gui.fedit(form, title = 'Image Resize')
        if results is None: return
        width, height, order = results

        factorx = width / shape[1]
        factory = height / shape[0]

        if source.ndim == 2:
            scaled = scipy.ndimage.zoom(source, (factory, factorx), order=order, mode="nearest")

        elif source.ndim == 3:
            #some bug here
            scaled = scipy.ndimage.zoom(source, (factory, factorx, 1.0), order=order, mode="nearest")
            #returned array dimensions are not on the expected index

        self.show_array(scaled)        