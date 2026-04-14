import platform
import numpy as np
import logging
from pathlib import Path
import time
import threading
import multiprocessing
from queue import Empty

logger = logging.getLogger(__name__)

from ...core.gui_proxy import GuiProxyBase, StaticGuiCall
from ... import gui, config
from ...utils.shared import SharedArray


def is_tuple_of_slices(obj):
    if not isinstance(obj, tuple): return False
    
    if True in [not isinstance(item, slice) for item in obj]: return False
    
    return True


class ViewerRoiAccess():

    def __init__(self, parent):
        self.parent = parent
        
        
    def keys(self):
        return self.parent.get_roi_names()
        
        
    def __getitem__(self, key):
        if isinstance(key, str):
            return self.parent.get_roi_array(key)            
        else:
            slices = self.parent.get_roi_slices(None)               
            return self.parent.vs[slices]
        
        
    def __setitem__(self, key, value):
        if isinstance(key, str):
            #How to set the color
            self.parent.add_roi_slices(key, value)
        
        elif is_tuple_of_slices(key) and isinstance(value, str):
            self.parent.add_roi_slices(value, key)
            
        else:            
            slices = self.parent.get_roi_slices(None)
            self.parent.vs[slices][key] = value
        
    
        
class ImageGuiProxy(GuiProxyBase):    
    category = 'image'
    opens_with = ['.tif', '.png', '.gif']
    
    def __init__(self):
        self.roi = ViewerRoiAccess(self)
        
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
    def set_clipboard_image(arr8bit):
        from ...utils.imconvert import process_ndarray_to_qimage_8bit
        
        cb = gui.qapp.clipboard()
        qimg = process_ndarray_to_qimage_8bit(arr8bit, 0, 1)
        cb.setImage(qimg)
        
        
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
    def show_array_cont(array=None, cmap=None, log=True, skip_init=False):                    
        
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

            panel.show_array(array, log=log, skip_init=skip_init)
        
        lock = gui._call_no_wait(_gui_show, array, cmap)
        return retries, lock
        

    @StaticGuiCall
    def show_mask(array=None, composition='sourceover', cmap=None, alpha=192):
        if not array is None:
            ImageGuiProxy.set_mask(array, composition, cmap, alpha)
            
        else:
            panel = gui.qapp.panels.selected('image')
            panel.imviewer.imgdata.show_layer('mask')    
            panel.imviewer.refresh()
        
        
    @StaticGuiCall
    def set_mask(array=None, composition='sourceover', cmap=None, alpha=192):
        panel = gui.qapp.panels.selected('image')       
        panel.imviewer.imgdata.set_mask(array, composition, cmap, alpha)
        panel.imviewer.refresh()
        
        
    @StaticGuiCall
    def hide_mask():
        panel = gui.qapp.panels.selected('image')
        panel.imviewer.imgdata.hide_layer('mask')        
        panel.imviewer.refresh()
        
    
    @StaticGuiCall
    def get_mask():
        panel = gui.qapp.panels.selected('image')
        if 'mask' in panel.imviewer.imgdata.layers:
            array = panel.imviewer.imgdata.layers['mask']['array']
            return array
        else:
            return None               
            
    @StaticGuiCall
    def init_mask(dtype='bool'):
        panel = gui.qapp.panels.selected('image')        
        
        if panel.imviewer.roi.isVisible():
            mask = np.ones((panel.imviewer.imgdata.height, panel.imviewer.imgdata.width), dtype=dtype)   
            slices = panel.imviewer.roi.selroi.getslices()
            mask[slices] = False
            
        else:
            mask = np.zeros((panel.imviewer.imgdata.height, panel.imviewer.imgdata.width), dtype=dtype)   
        
        ImageGuiProxy.set_mask(mask)
        return mask
        
       
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
        
    # @property    
    # def vr(self):
        # return self.get_image_view_region()

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
    def zoom_to_roi():
        """
        Zoom in to the roi
        """
        panel = gui.qapp.panels.selected('image')
        panel.zoomToRoi()          

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
    def hide_roi():
        panel = gui.qapp.panels.selected('image')
        panel.selectNone()
        
        
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
    def set_roi_mask(name, bmask, zero_origin=True, alpha=128):    
        panel = gui.qapp.panels.selected('image')
        
        if name in panel.imviewer.imgdata.chanstats:
            stats = panel.imviewer.imgdata.chanstats[name]
            stats.set_mask(bmask, zero_origin, alpha)
            panel.imviewer.refresh()
            
        else:
            raise KeyError(f'ROI name {name} not found')
            
        

    @StaticGuiCall
    def add_roi_slices(name, slices, color=None, active=True):
        """
        Add the region of interest on the current viewport.        
        
        :param tuple slices: Tuple of slices accross the dimensions.     
        """    
        panel = gui.qapp.panels.selected('image')
        
        if color is None:
            if name in panel.imviewer.imgdata.chanstats:
                color = panel.imviewer.imgdata.chanstats[name].plot_color
            
        if name in panel.imviewer.imgdata.pre_def_masks:
            raise KeyError(f'ROI name {name} is reserved')
            
        else:
            panel.imviewer.imgdata.addMaskStatistics(name, slices, color, active) 
            

    @StaticGuiCall
    def add_roi(name, slices=None, mask=None, color=None, active=True, zero_origin=True, alpha=128):
        
        if slices is None:
            slices = slice(None), slice(None)
            
        ImageGuiProxy.add_roi_slices(name, slices, color, active)
        
        if not mask is None:
            ImageGuiProxy.set_roi_mask(name, mask, zero_origin, alpha)            
            
            
    @StaticGuiCall
    def delete_roi(name):
        panel = gui.qapp.panels.selected('image')
        
        if name in panel.imviewer.imgdata.chanstats:
            panel.imviewer.imgdata.chanstats.pop(name)   
            panel.imviewer.refresh()
        
        
    @StaticGuiCall
    def is_roi_selected():
        panel = gui.qapp.panels.selected('image')
        return panel.imviewer.roi.isVisible()
        
        
    @StaticGuiCall
    def set_cfa(cfa='mono'):
        panel = gui.qapp.panels.selected('image')
        panel.setStatMasks(cfa)
        
        
    @StaticGuiCall
    def get_roi_names(actives=None, valid=True, skip_reserved=False):
        """
        Get the current region of interest as a tupple of slice objects
        """
        panel = gui.qapp.panels.selected('image')
        if panel is None: return []
        
        chstats = panel.imviewer.imgdata.chanstats
        
        if valid is None:
            roi_names = [k for k, v in chstats.items()]
        elif valid:
            roi_names = [k for k, v in chstats.items() if v.is_valid()]
        else:
            roi_names = [k for k, v in chstats.items() if not v.is_valid()]
            
        if skip_reserved:
            roi_names = [name for name in roi_names if not name in panel.imviewer.imgdata.PRE_DEF_MASK_NAMES]
            roi_names = [name for name in roi_names if not name.startswith('roi.')]

        if actives is None:
            return roi_names
        elif actives:
            return [k for k in roi_names if chstats[k].active]
        else:
            return  [k for k in roi_names if not chstats[k].active]
    

    @StaticGuiCall
    def get_roi_slices(name=None):
        """
        Get the current region of interest as a tupple of slice objects
        """
        panel = gui.qapp.panels.selected('image')
        if panel is None: return
        
        if name is None:
            return panel.imviewer.imgdata.selroi.getslices()
            
        else:
            chanstat = panel.imviewer.imgdata.chanstats.get(name, None)
            if chanstat is None:
                raise KeyError(f'{name} not found')
            return chanstat.slices
            
            
    @StaticGuiCall
    def get_roi_bmask(name=None, full=False):
        """
        Get the current region of interest as a tupple of slice objects
        """
        panel = gui.qapp.panels.selected('image')
        if panel is None: return
        
        chanstat = panel.imviewer.imgdata.chanstats.get(name, None)
        if chanstat is None:
            raise KeyError(f'{name} not found')
        
        if full:
            h, w = panel.imviewer.imgdata.height, panel.imviewer.imgdata.width
            slices = ImageGuiProxy.get_roi_slices(name)    
            roi_glbmask = np.ones((h, w), dtype='bool')
            roi_glbmask[slices] = chanstat.bmask
            return roi_glbmask
            
        else:
            return chanstat.mask_crop  
            
            
    @StaticGuiCall
    def get_roi_color(name=None):
        """
        Get the current region of interest as a tupple of slice objects
        """
        panel = gui.qapp.panels.selected('image')
        if panel is None: return
        
        chanstat = panel.imviewer.imgdata.chanstats.get(name, None)
        if chanstat is None:
            raise KeyError(f'{name} not found')

        c = chanstat.plot_color
        return (c.red(), c.green(), c.blue())
        

    @StaticGuiCall
    def get_roi_array(name=None):
        """
        Get the current region of interest as a tupple of slice objects
        """
        panel = gui.qapp.panels.selected('image')
        if panel is None: return
        
        chanstat = panel.imviewer.imgdata.chanstats.get(name, None)
        if chanstat is None:
            raise KeyError(f'{name} not found')
            
        return chanstat.roi            
            
            
    @StaticGuiCall
    def set_roi_active(name, active=True):
        """
        Enable or disable named roi
        """
        panel = gui.qapp.panels.selected('image')
        chanstat = panel.imviewer.imgdata.chanstats.get(name)
        
        if chanstat is None:
            raise KeyError(f'{name} not found')
            
        chanstat.active = active
        panel.imgprof.statsPanel.formatTable()   

        
    @StaticGuiCall
    def get_roi(name=None):
        """
        Get the region of interest of the current viewport as a tuple of integers.
        
        :return tuple(int, int, int, int): x0, y0, width, height.
        """
        if name is None:
            slices = ImageGuiProxy.get_roi_slices()
            x0 = slices[1].start
            width = slices[1].stop - x0
            y0 = slices[0].start
            height = slices[0].stop - y0
            return x0, y0, width, height
            
        slices = ImageGuiProxy.get_roi_slices(name)
        bmask = ImageGuiProxy.get_roi_bmask(name)
        color = ImageGuiProxy.get_roi_color(name)      
        roi = {'slices': slices, 'mask': bmask, 'zero_origin': False, 'color': color}   

        return roi        
        

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
        
    @StaticGuiCall  
    def screenshot(slices=None, zoom=None, show_masks=False):
        from ...utils.imconvert import qimage_to_ndarray
        panel = gui.qapp.panels.selected('image')
        qimg, props = panel.getViewerQImage(slices=slices, zoom=zoom, show_masks=show_masks)
        arr = qimage_to_ndarray(qimg)
        return arr, props       
        
    @staticmethod
    def high_pass_current_image():
        logger.error('Not implemented')    
        
    @staticmethod
    def get_distance():
        import math
        ImageGuiProxy.clear_pixel_click_queue()
        
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
        pixel_click_queue = ImageGuiProxy._get_pixel_click_queue()
        return pixel_click_queue.get()

    @staticmethod
    def clear_pixel_click_queue():
        pixel_click_queue = ImageGuiProxy._get_pixel_click_queue()
        while True:
            try:
                pixel_click_queue.get_nowait()
            except Empty:
                break
    
    @StaticGuiCall      
    def _get_pixel_click_queue(enable=True):
        panel = gui.qapp.panels.selected('image')
        return panel.imviewer.pixel_click_queue