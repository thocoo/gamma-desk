import pathlib
import collections
import threading
import math
from collections import UserDict

from qtpy import QtGui
from qtpy.QtGui import QImage
from qtpy.QtWidgets import QApplication

import numpy as np

import matplotlib as mpl

from ... import gui, config

from ...utils.shared import SharedArray
from ...utils import imconvert

from .dimensions import DimRanges
from . import fasthist
from ...dialogs.formlayout import fedit

here = pathlib.Path(__file__).absolute().parent

PLOT_COLORS = mpl.colormaps['tab10_r'](np.linspace(0, 1, 10)) * 255

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

PRE_DEF_MASK_NAMES = ['K', 'R', 'G', 'B', 'Gr', 'Gb']


def get_next_color_tuple():
    plot_color = tuple([int(round(ch)) for ch in PLOT_COLORS[0]])
    PLOT_COLORS[:] = np.roll(PLOT_COLORS, 1, axis=0)
    return plot_color
            
    
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
            if rng.start == rng.stop:
                rng.stop = rng.stop + 1
                
            elif rng.start > rng.stop:
                rng.start, rng.stop = rng.stop, rng.start

    def copy(self):
        s = SelectRoi(self.rngs[0].maxstop, self.rngs[1].maxstop)
        s.inherite(self)
        return s

        
    def update_statistics(self):
        if not self.update_statistics_func is None:
            self.update_statistics_func()
            
            
def int_none_repr(v):
    if v is None:
        return ''
    else:
        return v
        
        
class OrderedStats(UserDict):

    def __init__(self, *args, **kwargs):
        UserDict.__init__(self, *args, **kwargs)        
        self.order = []
        
    def __setitem__(self, key, value):
        self.data[key] = value
        
        if not key in self.order:
            self.order.append(key)
            
    def items(self):
        for key in self.order:
            yield key, self.data[key]


    def pop(self, key):
        self.order.remove(key)
        return self.data.pop(key)
        
        
    def clear(self):
        self.data.clear()
        self.order.clear()
        
    def get_position(self, key):
        return  self.order.index(key)
        
        
    def move_to_position(self, key, index=0):
        self.order.remove(key)
        self.order.insert(index, key)
            
            
    def move_to_end(self, key, last=True):
        if last:
            self.order.remove(key)
            self.order.append(key)
            
        else:        
            self.order.remove(key)
            self.order.insert(0, key)
            
    
            
        
class ImageStatistics(object):

    def __init__(self, imgdata, plot_color=None):
        self.imgdata = imgdata
        self._cache = dict()
        self.slices = None
        
        if plot_color is None:
            plot_color = get_next_color_tuple()
            
        if not isinstance(plot_color, QtGui.QColor):
            # Expect a typle of integers
            plot_color = QtGui.QColor(*plot_color)
            
        self.plot_color = plot_color
        
        self.dim = False
        self.active = True
        self.mask_visible = True
        self.plot_visible = True
        self.hist_visible = True

        
    def attach_full_array(self, slices):
        self.slices = slices
        self.clear()
        
        
    def slices_repr(self):
        return ','.join([f'{int_none_repr(slc.start)}:{int_none_repr(slc.stop)}:{int_none_repr(slc.step)}' for slc in self.slices])
        
        
    @property
    def full_array(self):
        return self.imgdata.statarr
        
        
    @property
    def roi(self):             
        min_ndim = min(len(self.slices), self.full_array.ndim)
        return self.full_array[self.slices[:min_ndim]]
        
        
    @property
    def dtype(self):
        return self.roi.dtype
        
                
    def is_valid(self):
        if not (self.imgdata.statarr is None) and \
            not (self.slices is None) and \
            not (self.roi.size == 0):
                return True
        else:        
            return False
        
        
    def clear(self):
        self._cache.clear()
        
        
    def step_for_bins(self, bins):
        if self.dtype in ['float16', 'float32', 'float64']:
            return math.ceil(65536 / bins) 
            
        if len(self._cache.keys()) == 0:
            self.calc_histogram()
            
        hist1 = self._cache['hist']  
        
        return math.ceil(len(hist1) / bins)
    
    
    def isCleared(self):
        return len(self._cache.keys()) == 0
    
        
    def histogram(self, step=1):
        if self.isCleared():
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
            hist, starts, stepsize = fasthist.hist16bit(self.roi, bins=None, step=1, use_numba=True)
            
        elif self.dtype in ['int32', 'uint32', 'int64', 'uint64', 'float16', 'float32', 'float64']:
            hist, starts, stepsize = fasthist.histfloat(self.roi, bins=65536, step=None, pow2snap=False, use_numba=True)
            
        self._cache['hist'] = hist
        self._cache['starts'] = starts
        self._cache['stepsize'] = stepsize            
    
    @property    
    def bins(self):
        return len(self.starts())
        
    def stepsize(self, step):
        return self._cache['stepsize'] * step
        
    def n(self):
        return np.prod(self.roi.shape)
        
    def sum(self):
        return (self.histogram() * self.starts()).sum()
        
    def mean(self):
        n = self.n()
        if n == 0:
            return np.nan
        return self.sum() / n

    def sumsq(self):
        return (self.histogram() * self.starts()**2).sum()
        
    def min(self):
        hist = self.histogram()
        starts = self._cache['starts']
        if len(starts) > 0:
            return starts[0]
        else:
            return np.nan
        
    def max(self):
        hist = self.histogram()
        starts = self._cache['starts']
        if len(starts) > 0:
            return starts[-1]
        else:
            return np.nan
        
    def std(self):
        n = self.n()
        
        if n >= 2:
            result = ((self.sumsq() - ((self.sum() * 1.0) ** 2) / n) / (n - 1))
            if result >= 0:
                return result ** 0.5
            else:
                return np.nan
        else:
            return np.nan
        
        
    def profile(self, axis=0):        
        roi = self.roi  
        array = self.full_array
        
        slices = self.slices
        
        if roi.nbytes == 0:
            return np.arange(0), np.arange(0)
        
        y = roi.mean(axis)        

        if y.ndim > 1:
            #Probably, still RGB split up
            y = y.mean(-1)
            
        x = np.arange(array.shape[1-axis])[slices[1-axis]]
        
        return x, y
        
        
def apply_roi_slice(large_slices, roi_slices):

    merged_slices = []
    
    large_ndim = len(large_slices)
    roi_ndim = len(roi_slices)
    
    if large_ndim > roi_ndim:
        roi_slices = list(roi_slices) + [slice(0, None, 1)]
        
    elif large_ndim < roi_ndim:
        large_slices = list(large_slices) + [slice(0, None, 1)]
        

    for large_slice, roi_slice in zip(large_slices, roi_slices):
          
        start = 0 if large_slice.start is None else large_slice.start
        step = 1 if large_slice.step is None else large_slice.step
        
        start = (roi_slice.start // step) * step + start
        stop = large_slice.stop if roi_slice.stop is None else roi_slice.stop
        
        sl = slice(start, stop, step)
        
        merged_slices.append(sl)            
        
    return tuple(merged_slices)
        

class ImageData:

    COLOR_K = {
        "Light": QtGui.QColor(0x40, 0x40, 0x40, 255),
        "Dark": QtGui.QColor(0xC0, 0xC0, 0xC0, 255),
    }

    def __init__(self):
        self.qimg = None
        self.map8 = None
        self.array = None
        self.imghist = ArrayHistory(config['image'].get("history_size", 500e6))
        
        arr = np.array([[0, 128], [128, 255]], 'uint8')
        
        self.selroi = SelectRoi(1, 1, self.update_roi_statistics)
        #self.custom_selroi = {}
        
        self.pre_def_masks = dict()
        self.chanstats = OrderedStats()
        self.cfa = 'mono'
        
        self.show_array(arr)        
        self.layers = collections.OrderedDict()
        
        
    def add_custom_selection(self, name):
        self.custom_selroi[name] = SelectRoi(self.height, self.width)
        
    
    def load_by_qt(self, path):
        self.qimg = QImage(str(path))
        
    def show_array(self, array=None, black=0, white=256, colormap=None, gamma=1, log=True, skip_init=False):
        threadcount = config['image']['threads'] 
        use_numba = config['image']['numba'] and has_numba        
        
    
        if array is None:
            #offset and gain adjust of current viewer
            pass
            
        elif isinstance(array, int) and array == -1:
            # Content of current array buffer has been updated
            # Re-evaluate the self.array
            for name, stat in self.chanstats.items():
                stat.clear()
            
        else:
            if log and not self.array is None:
                self.imghist.push(self.array)
            
            self.array = array                
            
            if not skip_init:
                self.init_channel_statistics(overwrite=False)
                
            else:
                for name, stat in self.chanstats.items():
                    stat.clear()
            
        #for selection in [self.selroi] + list(self.custom_selroi.values()):
        for selection in [self.selroi]:
            if selection.isfullrange():
                selection.xr.maxstop = self.width
                selection.yr.maxstop = self.height
                selection.reset()
            else:
                selection.xr.maxstop = self.width
                selection.yr.maxstop = self.height
                selection.clip()
               
        natrange = imconvert.natural_range(self.statarr.dtype)                   
        gain = natrange / (white - black)
        self.array8bit, self.qimg = imconvert.process_ndarray_to_qimage_8bit(
            self.statarr, black, gain, colormap, refer=True, shared=config["image"].get("qimg_shared_mem", False),
            gamma=gamma)
            
            
    def init_channel_statistics(self, mode=None, overwrite=True):
    
        if mode is None:
            if len(self.shape) == 2:
                mode = self.cfa
                
            else:
                mode = 'rgb'  

        # TO DO
        # It is not always needed to redefine masks and chanstats
        # masks and chanstats that are still valid should be kept
        
        self.defineModeMasks(mode)
                 
            
        for mask in list(self.chanstats.keys()):            
            chanstat = self.chanstats[mask]
            
            if mask.startswith('roi.'):
                prefix, mask = mask.split('.')
                prefix = prefix + '.'
                
            else:
                prefix = ''

            if mask in PRE_DEF_MASK_NAMES and overwrite:
                self.chanstats.pop(prefix + mask)
                
            elif mask in PRE_DEF_MASK_NAMES and not mask in self.pre_def_masks:
                self.chanstats.pop(prefix + mask)

            else:
                chanstat.clear()
            
        for mask in list(self.pre_def_masks.keys()):
            mask_props = self.pre_def_masks[mask]
            if not mask in self.chanstats:                            
                self.addMaskStatistics(mask, mask_props['slices'], mask_props['color'])
                self.chanstats[f'roi.{mask}'] = ImageStatistics(self, mask_props['roi.color'])
            
            
    def selectRoiOption(self, option: str):        
        if option == 'show roi only':
        
            for mask, mask_props in self.chanstats.items():
            
                if mask.startswith('roi.'):
                    mask_props.active = True
                    
                else:
                    mask_props.active = False   

        elif option == 'hide roi':
        
            for mask, mask_props in self.chanstats.items():
            
                if mask.startswith('roi.'):
                    mask_props.active = False
                    
                else:
                    mask_props.active = True               
                    
        else:
        
            for mask, mask_props in self.chanstats.items():
            
                mask_props.active = True
                
                
    def addMaskStatsDialog(self):
        selroi = self.selroi
        
        color = get_next_color_tuple()        
        color_str = '#' + ''.join(f'{v:02X}' for v in color[:3])
        
        i = 1
        while f'custom{i}' in self.chanstats:
            i += 1

        form = [('Name',  f'custom{i}'),
                ('Color',  color_str),
                ('x start', selroi.xr.start),
                ('x stop', selroi.xr.stop),
                ('x step', selroi.xr.step),
                ('y start', selroi.yr.start),
                ('y stop', selroi.yr.stop),
                ('y step', selroi.yr.step)]

        r = fedit(form, title='Add Mask Statistics')
        if r is None: return

        name = r[0]                
        color = QtGui.QColor(r[1])
        h_slice = slice(r[2], r[3], r[4])
        v_slice = slice(r[5], r[6], r[7])
        
        self.addMaskStatistics(name, (v_slice, h_slice), color)               


    def addMaskStatistics(self, name, slices, color=None, active=True):
        self.chanstats[name] = ImageStatistics(self, color)
        self.chanstats[name].attach_full_array(slices)
        self.chanstats[name].active = active
        
        
    def customMaskNames(self):
        return [mask for mask in self.chanstats if (not mask.startswith('roi.')) and (not mask in PRE_DEF_MASK_NAMES)]
        
        
    def find_chanstat_for_pixel(self, x, y):
    
        found = []
    
        for name, chanstat in self.chanstats.items():
            if name in PRE_DEF_MASK_NAMES: continue
            if name.startswith('roi.'): continue
            
            if y in range(*chanstat.slices[0].indices(self.height)) and \
                x in range(*chanstat.slices[1].indices(self.width)):
                found.append(name)
                
        for name in PRE_DEF_MASK_NAMES:
            if not name in self.chanstats: continue
            chanstat = self.chanstats[name]
            
            if y in range(*chanstat.slices[0].indices(self.height)) and \
                x in range(*chanstat.slices[1].indices(self.width)):
                found.append(name)
                
        return found
                    
    def defineModeMasks(self, mode='mono'):
        self.pre_def_masks.clear()
        mode = mode.lower()
        color_scheme = QApplication.instance().color_scheme

        if mode == 'mono':
            self.cfa = mode
            self.pre_def_masks = {
                'K': {'slices': (slice(None), slice(None)), 'color': self.COLOR_K[color_scheme], 'roi.color': QtGui.QColor(255, 0, 0, 255)}
            }
        
        elif mode == 'rgb':
            self.pre_def_masks = {
                'R':  {'slices': (slice(None), slice(None), slice(0, 1)), 'color': QtGui.QColor(255, 0, 0, 255), 'roi.color': QtGui.QColor(192, 0, 0, 255)},
                'G':  {'slices': (slice(None), slice(None), slice(1, 2)), 'color': QtGui.QColor(0, 255, 0, 255), 'roi.color': QtGui.QColor(64, 128, 0, 255)},
                'B':  {'slices': (slice(None), slice(None), slice(2, 3)), 'color': QtGui.QColor(0, 0, 255, 255), 'roi.color': QtGui.QColor(64, 0, 128, 255)}
                }
                
        elif mode in ['bg', 'gb', 'rg', 'gr']:
            c00 = (slice(0, None, 2), slice(0, None, 2))            
            c01 = (slice(0, None, 2), slice(1, None, 2))
            c10 = (slice(1, None, 2), slice(0, None, 2))        
            c11 = (slice(1, None, 2), slice(1, None, 2))
            
            self.cfa = mode
            
            red = QtGui.QColor(255, 0, 0, 255)
            teal = QtGui.QColor(0, 0x80, 0x80, 255)
            olive = QtGui.QColor(0x80, 0x80, 0, 255)
            blue = QtGui.QColor(0, 0, 255, 255)
            
            hot_red = QtGui.QColor(192, 0, 0, 255)
            hot_teal = QtGui.QColor(0x40, 0x60, 0x60, 255)
            hot_olive = QtGui.QColor(0xa0, 0x60, 0, 255)
            hot_blue = QtGui.QColor(0x40, 0, 0x80, 255)            
            
            
            if mode == 'bg':                    
                self.pre_def_masks = {
                    'B':  {'slices': c00, 'color': blue, 'roi.color': hot_blue}, 
                    'Gb': {'slices': c01, 'color': teal, 'roi.color': hot_teal}, 
                    'Gr': {'slices': c10, 'color': olive, 'roi.color': hot_olive},
                    'R':  {'slices': c11, 'color': red, 'roi.color': hot_red}}
        
            elif mode == 'gb':
                self.pre_def_masks = {
                    'Gb': {'slices': c00, 'color': teal, 'roi.color': hot_teal}, 
                    'B':  {'slices': c01, 'color': blue, 'roi.color': hot_blue}, 
                    'R':  {'slices': c10, 'color': red, 'roi.color': hot_red},
                    'Gr': {'slices': c11, 'color': olive, 'roi.color': hot_olive}}
            
            elif mode == 'rg':
                self.pre_def_masks = {
                    'R':  {'slices': c00, 'color': red, 'roi.color': hot_red},
                    'Gr': {'slices': c01, 'color': olive, 'roi.color': hot_olive},
                    'Gb': {'slices': c10, 'color': teal, 'roi.color': hot_teal}, 
                    'B':  {'slices': c11, 'color': blue, 'roi.color': hot_blue}}
            
            elif mode == 'gr':
                self.pre_def_masks = {
                    'Gr': {'slices': c00, 'color': olive, 'roi.color': hot_olive},
                    'R':  {'slices': c01, 'color': red, 'roi.color': hot_red},       
                    'B':  {'slices': c10, 'color': blue, 'roi.color': hot_blue}, 
                    'Gb': {'slices': c11, 'color': teal, 'roi.color': hot_teal}}            
        
    
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
        
        
    def set_mask(self, array=None, composition='sourceover', cmap='mask', alpha=255):
        self.set_layer('mask', array, composition, cmap, alpha)
        
        
    def set_layer(self, name, array=None, composition='sourceover', cmap='mask', alpha=255):
        if array is None:
            if name in self.layers.keys():
                self.layers.pop(name)
            return
            
        assert array.ndim == 2
        assert array.dtype in ['uint8', 'bool']
        
        height, width = array.shape
        
        compmode = COMPMODE[composition.lower()]            

        qimage = QImage(memoryview(array), width, height, width, QImage.Format_Indexed8)            
        qimage.setColorTable(imconvert.make_color_table(cmap, alpha))
        self.layers[name] = {'array': array, 'qimage': qimage, 'composition': compmode}                
        
        
    def update_roi_statistics(self):
        roi_slices = self.selroi.getslices()
        
        for mask_name, chanstat in list(self.chanstats.items()):  
        
            if mask_name.startswith('roi.'): 
                mask_name = mask_name[4:]
                
            else:
                continue
            
            large_slices = self.pre_def_masks[mask_name]['slices']            
            merged_slices = apply_roi_slice(large_slices, roi_slices)            
            chanstat.attach_full_array(merged_slices)  
            

    def disable_roi_statistics(self):
    
        for mask_name, chanstat in list(self.chanstats.items()):          
            if not mask_name.startswith('roi.'): continue
            chanstat.attach_full_array(None)
            

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
            
            
    def selectChannelStat(self, statsNames):
    
        for name, chanstat in self.chanstats.items():
            if len(statsNames) == 0 or name in statsNames:
                chanstat.dim = False  
            else:
                chanstat.dim = True        
            
        
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