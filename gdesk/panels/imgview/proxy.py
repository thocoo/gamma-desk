import platform
import numpy as np
import logging
from pathlib import Path
import time
import threading
import multiprocessing

logger = logging.getLogger(__name__)

from ...core.gui_proxy import GuiProxyBase, StaticGuiCall
from ... import gui, config
from ...utils.shared import SharedArray
        
class ImageGuiProxy(GuiProxyBase):    
    category = 'image'
    opens_with = ['.tif', '.png', '.gif']
    
    def __init__(self):
        pass
        
    def attach(self, gui):
        gui.img = self   
        
        # Properties are defined on gui 
        
        gui.set_roi = self.set_roi
        gui.set_roi_slices = self.set_roi_slices
        gui.get_roi = self.get_roi
        gui.get_roi_slices = self.get_roi_slices
        gui.jump_to = self.jump_to
        gui.zoom_fit = self.zoom_fit
        gui.zoom_full = self.zoom_full
        gui.zoom_region = self.zoom_region
        gui.get_clipboard_image = self.get_clipboard_image
        
        return 'img'
        
    @StaticGuiCall
    def new(cmap=None, viewtype='image-profile', title=None, size=None, empty=True):
        panel = GuiProxyBase._new('image', viewtype, size=size, empty=empty)
        
        if not cmap is None:
            panel.colormap = cmap        
            
        if not title is None:
            panel.long_title = title
            
        return panel.panid
    
    @StaticGuiCall    
    def open(filepath, new=False):
        if new:
            ImageGuiProxy.new()
            panel = gui.qapp.panels.selected('image')
        else:
            panel = gui.qapp.panels.selected('image')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('image', defaulttype = 'image-profile', empty=True)
        panel.openImage(filepath)
        window = panel.get_container().parent()
        window.raise_()
        gui.qapp.processEvents()
        return panel.panid
        
    @StaticGuiCall    
    def open_array(array, new=False):
        if new:
            ImageGuiProxy.new()
            panel = gui.qapp.panels.selected('image')
        else:
            panel = gui.qapp.panels.selected('image')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('image', defaulttype = 'image-profile', empty=True)
        
        panel.show_array(array)
        
        window = panel.get_container().parent()
        window.raise_()
        gui.qapp.processEvents()
        return panel.panid        
        
    @StaticGuiCall    
    def get_clipboard_image():
        from ...utils.imconvert import qimage_to_ndarray
        
        cb = gui.qapp.clipboard()
        md = cb.mimeData()
        qimg = md.imageData()
        if qimg is None:
            logger.error('No image data on clipboard')
            return
        arr = qimage_to_ndarray(qimg)
        return arr              
        
    @StaticGuiCall
    def select(panid=-1):
        """
        Select or create an image panel with id image_id or auto id
        """        
        panel = gui.qapp.panels.select_or_new('image', panid, defaulttype='image-profile')
        return panel.panid
    
    def show(self, array, cmap=None, wait=True):   
        """
        Show array in the image viewer.
        
        :param ndarray array: 
        :param str cmap: 'grey', 'jet' or 'turbo'
        """
        
        if wait:
            shwarr = ImageGuiProxy.show_array
            
        else:
            shwarr = ImageGuiProxy.show_array_cont    
        
        if config['image']['queue_array_shared_mem']:            
            if self.current_image_is_shared():
                current_array = self.get_image_view_source()
                if current_array.shape == array.shape and current_array.dtype == array.dtype:
                    current_array[:] = array
                    return shwarr(-1, cmap)
                else:
                    sharray = SharedArray(array.shape, array.dtype)
                    sharray[:] = array                
                    return shwarr(sharray, cmap)
            else:            
                sharray = SharedArray(array.shape, array.dtype)
                sharray[:] = array                
                return shwarr(sharray, cmap)                
        else:
            return shwarr(array.copy(), cmap)

    @StaticGuiCall
    def show_array(array=None, cmap=None):
        panel = gui.qapp.panels.selected('image')

        if not cmap is None:
            panel.colormap = cmap        

        panel.show_array(array)
        return panel.panid


    @staticmethod
    def show_array_cont(array=None, cmap=None):                    
        
        retries = 0
        
        if not gui.call_queue is None:
            q = gui.call_queue
            
        else:
            q = gui._qapp.handover.signal_call_queue
            
        while not q.empty():
            time.sleep(0.01)   
            retries += 1            
        
        def _gui_show(array, cmap):
            panel = gui.qapp.panels.selected('image')

            if not cmap is None:
                panel.colormap = cmap        

            panel.show_array(array)
        
        gui._call_no_wait(_gui_show, array, cmap)
        return retries
        
    
    @StaticGuiCall    
    def show_mask(array=None, composition='sourceover'):
        panel = gui.qapp.panels.selected('image')
        panel.imviewer.imgdata.set_mask(array, composition)
        panel.imviewer.refresh()
       
    def refresh(self):
        ImageGuiProxy.show_array()        

    @StaticGuiCall
    def cmap(cmap):
        ImageGuiProxy.show_array(None, cmap)
        
    @property    
    def vs(self):
        array = self.get_image_view_source()
        if isinstance(array, SharedArray):
            return array.ndarray            
            
        else:
            return array
        
    @property    
    def vr(self):
        return self.get_image_view_region()

    @property    
    def buff(self):
        return self.get_image_view_buffer()         
        
    @StaticGuiCall
    def get_image_view_source():            
        panel = gui.qapp.panels.selected('image')
        if panel is None: return        
        return panel.srcarray
    
    @StaticGuiCall    
    def current_image_is_shared():
        panel = gui.qapp.panels.selected('image')
        if panel is None: return        
        return isinstance(panel.srcarray, SharedArray)
        
    def get_image_view_region(self):
        slices =  self.get_roi_slices()
        if slices is None: return None
        vs = self.get_image_view_source()
        if vs is None: return
        return vs[slices] 
        
    @StaticGuiCall
    def get_image_view_buffer():
        panel = gui.qapp.panels.selected('image')
        if panel is None: return None
        return panel.imviewer.imgdata.array8bit
        
    @StaticGuiCall
    def repaint():
        panel = gui.qapp.panels.selected('image')
        panel.imviewer.refresh()
        
    @StaticGuiCall
    def set_range(black, white):
        panel = gui.qapp.panels.selected('image')
        panel.changeBlackWhite(black, white)                   
        
    @StaticGuiCall
    def set_offset_gain(offset=0, gain=1, gamma=1, as_default=False):
        panel = gui.qapp.panels.selected('image')
        panel.changeOffsetGain(offset, gain, gamma, True)
        if as_default:
            panel.setCurrentOffsetGainAsDefault()
            
    @staticmethod
    def read_raw(data, width, height, depth=1, dtype='uint8', offset=0, byteswap=False):
        if isinstance(data, (str, Path)):
            fp = open(data, 'br')
            data = fp.read()
            fp.close()
        
        dtype = np.dtype(dtype)

        leftover = len(data) - (width * height  * dtype.itemsize + offset)

        if leftover > 0:
            print('Too much data found (%d bytes too many)' % leftover)

        elif leftover < 0:
            print('Not enough data found (missing %d bytes)' % (-leftover))

        arr = np.ndarray(shape=(height, width), dtype=dtype, buffer=data[offset:])
        
        if byteswap:
            arr = arr.byteswap()
        
        return arr
        
    @staticmethod
    def close_all():
        while ImageGuiProxy.close():
            pass
        
    @StaticGuiCall
    def zoom_fit():
        """
        Zoom the image to fitting the image viewer area.
        Snap on the default zooming values.
        """
        panel = gui.qapp.panels.selected('image')
        panel.zoomFit()

    @StaticGuiCall
    def zoom_full():
        """
        Zoom the image to fully fitting the image viewer area.
        """
        panel = gui.qapp.panels.selected('image')
        panel.zoomFull()  

    @StaticGuiCall
    def zoom_region(x, y, width, height):
        """
        Zoom the image to a certain region.
        """
        panel = gui.qapp.panels.selected('image')
        panel.zoomToRegion(x, y, width, height) 

    @StaticGuiCall
    def jump_to(x, y):
        """
        Select a certain pixel and zoom to it
        """ 
        panel = gui.qapp.panels.selected('image')
        panel.jumpTo(x, y)        
        
    @StaticGuiCall
    def set_roi_slices(slices, yonfirst=True):
        """
        Set the region of interest on the current viewport.        
        
        :param tuple slices: Tuple of slices accross the dimensions.
        :param bool yonfirst: True if first slice is the y direction.
        """        
        panel = gui.qapp.panels.selected('image')
        roi = panel.imviewer.roi
        selroi = panel.imviewer.imgdata.selroi        
        
        if yonfirst:
            selroi.xr.setfromslice(slices[1])
            selroi.yr.setfromslice(slices[0])        
        else:
            selroi.xr.setfromslice(slices[0])
            selroi.yr.setfromslice(slices[1])
        
        roi.clip()
        roi.show()
        roi.roiChanged.emit()    
        
    @StaticGuiCall
    def set_roi(x0, y0, width=1, height=1):
        """
        Set the region of interest on the current viewport.
        
        :param int x0: first column of the roi
        :param int y0: first row of the roi
        :param int width: width of the roi
        :param int height: height of the roi        
        """    
        panel = gui.qapp.panels.selected('image')
        roi = panel.imviewer.roi
        roi.setStartEndPoints(x0, y0, x0 + width - 1, y0 + height - 1)        
        roi.show()
        roi.roiChanged.emit()      

    @StaticGuiCall
    def get_roi_slices():
        """
        Get the current region of interest as a tupple of slice objects
        """
        panel = gui.qapp.panels.selected('image')
        if panel is None: return
        return panel.imviewer.imgdata.selroi.getslices()
        
    @StaticGuiCall
    def get_roi():
        """
        Get the region of interest of the current viewport as a tuple of integers.
        
        :return tuple(int, int, int, int): x0, y0, width, height.
        """
        slices = ImageGuiProxy.get_roi_slices()
        x0 = slices[1].start
        width = slices[1].stop - x0
        y0 = slices[0].start
        height = slices[0].stop - y0
        return x0, y0, width, height   

    @property
    def vr(self):
        slices =  self.get_roi_slices()
        return self.vs[slices]        
        
    @staticmethod
    def mirror_x():
        print('mirror_x started')
        arr = gui.vs.copy()
        arr = arr[:,::-1]
        gui.img.new()
        gui.img.show(arr)        
        print('mirror_x ended')
        
    @staticmethod
    def high_pass_current_image():
        logger.error('Not implemented')    
        
    @staticmethod
    def get_distance():
        import math
        
        print('Select first point: ', end='')
        p1 = ImageGuiProxy.get_selected_pixel()
        print(p1)
        print('Select second point: ', end='')
        p2 = ImageGuiProxy.get_selected_pixel()
        print(p2)
        delta = (p2[0] - p1[0], p2[1] - p1[1])
        print(f'delta xy: {delta}')
        print(f'delta  r: {(delta[0]**2 + delta[1]**2) ** 0.5:.5g}')
        if delta[0] == 0:
            print(f'angle  r: {90}')
        else:
            print(f'angle  r: {math.atan(delta[1]/delta[0]) * 180 / 3.141592:.5g}')
            
    @staticmethod
    def get_selected_pixel():        
        ImageGuiProxy._push_selected_pixel_queue(True)
        pixel = input()
        return eval(pixel)            
    
    @StaticGuiCall      
    def _push_selected_pixel_queue(enable=True):
        panel = gui.qapp.panels.selected('image')
        panel.imviewer.push_selected_pixel = enable