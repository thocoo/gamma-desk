import pathlib
import collections
import queue
import threading
import math

from qtpy import QtGui, QtCore
from qtpy.QtGui import QImage

import numpy as np

from ... import gui, config

from ...utils.shared import SharedArray
from ...utils import imconvert

from .dimensions import DimRanges
from . import fasthist

here = pathlib.Path(__file__).absolute().parent

try:
    from .numba_func import map_values_mono, map_values_rgbswap, map_values_rgb
    has_numba = True
    
except:
    has_numba = False

#https://doc.qt.io/qtforpython-5.12/PySide2/QtGui/QPainter.html#composition-modes
COMPMODE = dict()    
COMPMODE['sourceover'] = QtGui.QPainter.CompositionMode_SourceOver    
COMPMODE['plus'] = QtGui.QPainter.CompositionMode_Plus   
COMPMODE['multiply'] = QtGui.QPainter.CompositionMode_Multiply   
COMPMODE['screen'] = QtGui.QPainter.CompositionMode_Screen  
COMPMODE['overlay'] = QtGui.QPainter.CompositionMode_Overlay  
COMPMODE['darken'] = QtGui.QPainter.CompositionMode_Darken  
COMPMODE['lighten'] = QtGui.QPainter.CompositionMode_Lighten 
    
class SelectRoi(DimRanges):

    """
    Selection widget range data.
    """

    def __init__(self, height, width, update_statistics_func=None):
        DimRanges.__init__(self, (height, width))
        self.update_statistics_func = update_statistics_func
        
    @property
    def yr(self):
        return self.rngs[0]
    
    @property    
    def xr(self):
        return self.rngs[1]

    def ensure_rising(self):
        for rng in self.rngs:
            if rng.start > rng.stop:
                rng.start, rng.stop = rng.stop, rng.start

    def copy(self):
        s = SelectRoi(self.rngs[0].maxstop, self.rngs[1].maxstop)
        s.inherite(self)
        return s
        
    def update_statistics(self):
        if not self.update_statistics_func is None:
            self.update_statistics_func()
        
class ImageStatistics(object):

    def __init__(self):
        self._cache = dict()
        self.arr2d = None        
        
    def attach_arr2d(self, arr2d):
        self.arr2d = arr2d
        self.clear()
        
    @property
    def dtype(self):
        return self.arr2d.dtype        
        
    def clear(self):
        self._cache.clear()
        
    def step_for_bins(self, bins):
        if self.dtype in ['float16', 'float32', 'float64']:
            return math.ceil(65536 / bins) 
            
        if len(self._cache.keys()) == 0:
            self.calc_histogram()
            
        hist1 = self._cache['hist']  
        
        return math.ceil(len(hist1) / bins)
        
    def histogram(self, step=1):
        if len(self._cache.keys()) == 0:
            self.calc_histogram()
        
        hist1 = self._cache['hist']      
            
        if step > 1:
            bins = len(hist1) // step
            left = len(hist1) % step
            tmp = hist1[:step*bins]            
            if left > 0:
                hist = np.r_[tmp.reshape(bins, step).sum(1), hist1[step*bins:].sum()]                
            else:
                hist = tmp.reshape(bins, step).sum(1)
            return hist
        else:
            return hist1       
        
    def starts(self, step=1):
        if len(self._cache.keys()) == 0:
            self.calc_histogram()
            
        starts1 = self._cache['starts'] 

        if step > 1:
            return starts1[::step]
        else:        
            return starts1      
    
    def calc_histogram(self, bins=None, step=None):  
        if self.dtype in ['int8', 'uint8', 'int16', 'uint16']:
            hist, starts, stepsize = fasthist.hist16bit(self.arr2d, bins=None, step=1, use_numba=True)
            
        elif self.dtype in ['int32', 'uint32', 'int64', 'uint64', 'float16', 'float32', 'float64']:
            hist, starts, stepsize = fasthist.histfloat(self.arr2d, bins=65536, step=None, pow2snap=False, use_numba=True)
            
        self._cache['hist'] = hist
        self._cache['starts'] = starts
        self._cache['stepsize'] = stepsize            
    
    @property    
    def bins(self):
        return len(self.starts())
        
    def stepsize(self, step):
        return self._cache['stepsize'] * step
        
    def n(self):
        return self.arr2d.shape[0] * self.arr2d.shape[1]
        
    def sum(self):
        return (self.histogram() * self.starts()).sum()
        
    def mean(self):
        return self.sum() / self.n()

    def sumsq(self):
        return (self.histogram() * self.starts()**2).sum()
        
    def min(self):
        non_zeros_indices = np.argwhere(self.histogram() > 0)
        min_index = non_zeros_indices[0][0]
        max_index = non_zeros_indices[-1][0]
        return self.starts()[min_index]
        
    def max(self):
        non_zeros_indices = np.argwhere(self.histogram() > 0)
        max_index = non_zeros_indices[-1][0]
        return self.starts()[max_index]     
        
    def std(self):
        n = self.n()
        result = ((self.sumsq() - ((self.sum() * 1.0) ** 2) / n) / (n - 1)) ** 0.5
        return result
        

class ImageData(object):        
    def __init__(self):
        self.qimg = None
        self.map8 = None
        self.array = None
        self.imghist = ArrayHistory(config['image'].get("history_size", 500e6))
        
        arr = np.ones((1,1),'uint8') * 128
        self.selroi = SelectRoi(1, 1, self.update_roi_statistics)
        self.chanstats = dict()
        
        self.show_array(arr)
        self.layers = collections.OrderedDict()
    
    def load_by_qt(self, path):
        self.qimg = QImage(str(path))
        
    def show_array(self, array=None, black=0, white=256, colormap=None, gamma=1, log=True):
        with gui.qapp.waitCursor():
            threadcount = config['image']['threads'] 
            use_numba = config['image']['numba'] and has_numba        
            
        
            if array is None:
                #offset and gain adjust of current viewer
                pass
                
            elif isinstance(array, int) and array == -1:
                #Content of current array has been updated
                for name, stat in self.chanstats.items():
                    stat.clear()
                
            else:
                if log and not self.array is None:
                    self.imghist.push(self.array)
                
                self.array = array                    
                self.chanstats.clear()
                    
                if len(self.shape) == 2:
                    self.chanstats['K'] = ImageStatistics()
                    self.chanstats['K'].attach_arr2d(self.statarr)
                    self.chanstats['RK'] = ImageStatistics()
                    self.update_roi_statistics()
                    
                else:
                    self.chanstats['R'] = ImageStatistics()
                    self.chanstats['G'] = ImageStatistics()
                    self.chanstats['B'] = ImageStatistics()
                    self.chanstats['R'].attach_arr2d(self.statarr[:,:,0])
                    self.chanstats['G'].attach_arr2d(self.statarr[:,:,1])
                    self.chanstats['B'].attach_arr2d(self.statarr[:,:,2])                   
                    self.chanstats['RR'] = ImageStatistics()
                    self.chanstats['RG'] = ImageStatistics()
                    self.chanstats['RB'] = ImageStatistics()
                    self.update_roi_statistics()
                
            if self.selroi.isfullrange():
                self.selroi.xr.maxstop = self.width
                self.selroi.yr.maxstop = self.height
                self.selroi.reset()
            else:
                self.selroi.xr.maxstop = self.width
                self.selroi.yr.maxstop = self.height
                self.selroi.clip()
                   
            natrange = imconvert.natural_range(self.statarr.dtype)                   
            gain = natrange / (white - black)
            self.array8bit, self.qimg = imconvert.process_ndarray_to_qimage_8bit(
                self.statarr, black, gain, colormap, refer=True, shared=config["image"].get("qimg_shared_mem", False),
                gamma=gamma)
    
    @property    
    def statarr(self):
        if isinstance(self.array, SharedArray):
            return self.array.ndarray            
        else:
            return self.array
            
    @property
    def shape(self):
        return self.statarr.shape            
             
    @property
    def height(self):
        return self.shape[0]
        
    @property
    def width(self):
        return self.shape[1]        
        
        
    def get_natural_range(self):
        return imconvert.natural_range(self.statarr.dtype)
        
    def set_mask(self, array=None, composition='sourceover'):
        self.set_layer('mask', array, composition)        
        
    def set_layer(self, name, array=None, composition='sourceover'):
        if array is None:
            if name in self.layers.keys():
                self.layers.pop(name)
            return
            
        assert array.ndim == 2
        assert array.dtype in ['uint8', 'bool']
        
        height, width = array.shape
        
        compmode = COMPMODE[composition.lower()]
            
        qimage = QImage(memoryview(array), width, height, width, QImage.Format_Indexed8)
        qimage.setColorTable(imconvert.make_color_table('mask'))
        self.layers[name] = {'array': array, 'qimage': qimage, 'composition': compmode}                
        
        
    def update_roi_statistics(self):
        slices = self.selroi.getslices()
            
        clr_slices = {'RK': slices,
            'RR': (slices[0], slices[1], 0),
            'RG': (slices[0], slices[1], 1),
            'RB': (slices[0], slices[1], 2)}
            
        for clr, chanstat in self.chanstats.items():  
            if not clr in clr_slices.keys(): continue
            chanstat.attach_arr2d(self.statarr[clr_slices[clr]])

    def update_array8bit_by_slices(self, slices):
        def takemap(source_slice, target_slice):
            self.array8bit[target_slice] = np.take(self.map8, self.statarr[source_slice])
        
        threads = []
        for (source_slice,  target_slice) in slices:
            threads.append(threading.Thread(target=takemap, args=(source_slice, target_slice)))
        
        for thread in threads:
            thread.start()
            
        for thread in threads:
            thread.join()               
        
    def get_number_of_bytes(self): 
        nbytes = 0
        nbytes += self.statarr.nbytes
        nbytes += self.array8bit.nbytes
        return nbytes
        
class ArrayHistory(object):

    def __init__(self, max_size=4):
        self.max_size = max_size 
        self.prior_arrays = []
        self.next_arrays = []
        
    def push(self, array):
        overflow = self.reduce_size_to_max_byte_size(array.size)  
        if overflow < 0: self.prior_arrays.append(array)
        self.next_arrays.clear()        
        
    def reduce_size_to_max_byte_size(self, add_size=0):
        current_size = add_size
        for arr in self.prior_arrays:
            current_size += arr.size
        overflow = current_size - self.max_size
        while overflow > 0 and len(self.prior_arrays) > 0:
            array = self.prior_arrays.pop(0)            
            overflow -= array.size        
        return overflow
        
    def prior(self, current_array):
        array = self.prior_arrays.pop(-1)
        self.next_arrays.append(current_array)
        return array
        
    def next(self, current_array):
        array = self.next_arrays.pop(-1)
        self.prior_arrays.append(current_array)  
        return array
        
    def __len__(self):
        return len(self.prior_arrays) + len(self.next_arrays)
        
    def prior_length(self):
        return len(self.prior_arrays)
        
    def next_length(self):
        return len(self.next_arrays)        
        
    def clear(self):
        self.stack.clear()