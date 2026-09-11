import logging
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np

from ...panels import CheckMenu
from ...gcore.utils import ActionArguments
from ...utils import clip_array
from ...utils import imconvert

from ... import config, gui

respath = Path(config['respath'])

class ImageEditMenu(CheckMenu):

    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)
        
        self.basePanel = basePanel

        basePanel.addMenuItem(self, 'Swap RGB | BGR', self.swapRGB,
            statusTip="Swap the blue with red channel",
            icon = str(respath / 'icons' / 'px16' / 'color.png'))
            
        basePanel.addMenuItem(self, 'to Monochrome', self.toMonochrome,
            statusTip="Convert an RGB image to monochrome grey",
            icon = str(respath / 'icons' / 'px16' / 'convert_color_to_gray.png'))
            
        basePanel.addMenuItem(self, 'to Photometric Monochrome', self.toPhotoMonochrome,
            statusTip="Convert an RGB image to photometric monochrome grey",
            icon = str(respath / 'icons' / 'px16' / 'convert_color_to_gray.png'))
            
        basePanel.addMenuItem(self, 'to 8-bit', self.to8bit,
            enablecall = self.is16bit)
            
        basePanel.addMenuItem(self, 'to 16-bit', self.to16bit,
            enablecall = self.is8bit)
            
        basePanel.addMenuItem(self, 'to Data Type', self.to_dtype)
        
        basePanel.addMenuItem(self, 'Swap MSB LSB Bytes', self.swapbytes,
            enablecall = self.is16bit)
        
        basePanel.addMenuItem(self, 'Fill...'          , self.fillValue,
            statusTip="Fill the image with the same value",
            icon = str(respath / 'icons' / 'px16' / 'paintcan.png'))
            
        basePanel.addMenuItem(self, 'Add noise...'     , self.addNoise,
            statusTip="Add Gaussian noise")
            
        basePanel.addMenuItem(self, 'Invert', self.invert,
            statusTip="Invert the image")
            
        basePanel.addMenuItem(self, 'Adjust Lighting...', self.adjustLighting,
            statusTip="Adjust the pixel values",
            icon = str(respath / 'icons' / 'px16' / 'contrast.png'))
            
        basePanel.addMenuItem(self, 'Adjust Gamma...', self.adjustGamma,
            statusTip="Adjust the gamma")
            
            
    @property
    def ndarray(self):
        return self.basePanel.ndarray
        
        
    @property
    def offset(self):
        return self.basePanel.offset            


    @property
    def gain(self):
        return self.basePanel.gain                    
        
        
    def is8bit(self):
        return self.basePanel.ndarray.dtype in ['uint8', 'int8']
        
    
    def is16bit(self):
        return self.basePanel.ndarray.dtype in ['uint16', 'int16']        
        
        
    def show_array(self, array):
        self.basePanel.show_array(array)        
        
        

    def fillValue(self):
        """
        :param float value:
        """
        with ActionArguments(self) as args:
            args['value'] = 0.0

        if args.isNotSet():
            form = [('Value', args['value'])]
            results = gui.fedit(form, title='Fill Value')
            if results is None: return
            args['value'] = results[0]

        procarr = self.ndarray.copy()
        procarr[:] = args['value']
        self.show_array(procarr)


    def addNoise(self):
        form = [('Standard Deviation', 1.0)]
        results = gui.fedit(form, title='Add Noise')
        if results is None: return
        std = float(results[0])

        def run_in_console(std):
            arr = gui.vs
            shape = arr.shape
            dtype = arr.dtype            
            procarr = clip_array(arr + np.random.randn(*shape) * std + 0.5, dtype)
            gui.show(procarr)
            
        panel = gui.qapp.panels.selected('console')
        panel.task.call_func(run_in_console, args=(std,))


    def invert(self):
        procarr =  ~self.ndarray
        self.show_array(procarr)
        

    def swapRGB(self):
        if not self.ndarray.ndim >= 3:
            gui.dialog.msgbox('The image has not 3 or more channels', icon='error')
            return
        procarr = self.ndarray.copy()
        procarr[:,:,0] = self.ndarray[:,:,2]
        procarr[:,:,1] = self.ndarray[:,:,1]
        procarr[:,:,2] = self.ndarray[:,:,0]
        self.show_array(procarr)


    def toMonochrome(self):
        array = self.ndarray

        if not array.ndim == 3:
            return

        dtype = array.dtype
        procarr = clip_array(array.mean(2), dtype)
        self.show_array(procarr)


    def toPhotoMonochrome(self):
        array = self.ndarray

        if not array.ndim == 3:
            return

        clip_low, clip_high = imconvert.integer_limits(array.dtype)
        mono = np.dot(array, [0.299, 0.587, 0.144])
        procarr = clip_array(mono, array.dtype)
        self.show_array(procarr)
        
        
    def is8bit(self):
        return self.ndarray.dtype in ['uint8', 'int8']
        
    
    def is16bit(self):
        return self.ndarray.dtype in ['uint16', 'int16']
        
        
    def to8bit(self):
        if not self.is16bit(): return
        self.show_array((self.ndarray >> 8).astype('uint8'))
        
        
    def to16bit(self):
        if not self.is8bit(): return
        self.show_array(self.ndarray.astype('uint16') << 8)
        
        
    def to_dtype(self):
        dtypes = ['uint8', 'uint16', 'double']
        scales = ['bit shift', 'clip']
        
        form = [
            ('Data Type', [1] + dtypes),
            ('Scale', [1] + scales)]
            
        results = gui.fedit(form, title='Convert Data Type')
        if results is None: return
        dtype = dtypes[results[0]-1]
        scale = scales[results[1]-1]
        
        array = gui.vs
        if scale == 'clip' and dtype in ['uint8', 'uint16']:
            if dtype == 'uint8':
                lower, upper = 0, 255
                
            elif dtype == 'uint16':
                lower, upper = 0, 65535
                
            array = array.clip(lower, upper)
            array = array.astype(dtype)
            
        elif scale == 'bit shift' and dtype in ['uint8', 'uint16']:
            if array.dtype == 'uint8' and dtype == 'uint16':
                array = gui.vs.astype(dtype)
                array <<= 8
                
            elif array.dtype == 'uint16' and dtype == 'uint8':
                array >>= 8                
                array = gui.vs.astype(dtype)
            
        else:
            array = array.astype(dtype)
            
        gui.show(array)
        
        
        
    def swapbytes(self):
        gui.show(gui.vs.byteswap())
        

    def adjustLighting(self):
        """
        :param float offset:
        :param float gain:
        """
        with ActionArguments(self) as args:
            args['offset'] = -self.offset * 1.0
            args['gain'] = self.gain * 1.0

        if args.isNotSet():
            form = [('Offset', args['offset']),
                    ('Gain', args['gain'])]

            results = gui.fedit(form, title='Adjust Lighting')
            if results is None: return
            offset, gain = results

        else:
            offset, gain = args['offset'], args['gain']

        #TO DO: use value mapping if possible
        array = self.ndarray
        procarr = clip_array(array * gain + offset, array.dtype)
        self.show_array(procarr)


    def adjustGamma(self):
        """
        :param float gamma:
        :param float upper:
        """
        with ActionArguments(self) as args:
            args['gamma'] = 1.0
            args['upper'] = 255

        if args.isNotSet():
            form = [('Gamma', args['gamma']),
                    ('Upper', args['upper'])]

            results = gui.fedit(form, title='Adjust Gamma')
            if results is None: return
            gamma, upper = results

        else:
            gamma, upper = args['gamma'], args['upper']

        #TO DO: use value mapping if possible
        array = self.ndarray
        procarr = clip_array(np.power(array, gamma) * upper ** (1-gamma), array.dtype)
        self.show_array(procarr)        