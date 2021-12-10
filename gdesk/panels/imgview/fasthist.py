import sys
import math
import logging

import numpy as np

try:
    from ...utils import numba_func
    has_numba = True
except:
    has_numba = False    
    
logger = logging.getLogger(__name__)

def is_integer_num(n):
    if isinstance(n, int):
        return True
    if isinstance(n, float):
        return n.is_integer()
    return False
    
def natural_range(dtype):
    if dtype in ['uint8', 'int8']:
        return 256
    elif dtype in ['uint16', 'int16']:
        return 65536
    elif dtype in ['uint32', 'int32']:
        return 4294967296
    elif dtype in ['uint64', 'int64']:
        return 18446744073709551616
    elif dtype in ['float16', 'float32', 'float64']:
        return 1
    else:
        raise TypeError('dtype %s not supported to display' % str(statbuff.dtype))
        
def get_map16(dtype='float64', offset=0, gain=1):
    natrange = natural_range(dtype)
    return ((np.arange(natrange) - offset) * gain * 65536 / natrange).clip(0, 65536).astype('uint16')    

def hist2d(array, bins=64, step=None, low=None, high=None, pow2snap=True, plot=False, use_numba=True):
    if array.dtype in ['int8', 'uint8', 'int16', 'uint16']:
        assert pow2snap
        hist, starts, stepsize = hist16bit(array, bins, step, low, high, use_numba=True)
        return hist, starts, stepsize
        
    elif array.dtype in ['float16', 'float32', 'float64']:
        hist, starts, stepsize = histfloat(array, bins, step, low, high, pow2snap)
        return hist, starts, stepsize        
        
    if plot:
        plt.bar(starts + stepsize/2, hist, stepsize)
        plt.grid()
        plt.xlabel('value [DN]')
        plt.ylabel('count')        
    
    return hist, starts, stepsize
    
def hist16bit(array, bins=64, step=None, low=None, high=None, use_numba=True):
    """
    stepsize should be power of 2    
    array should be 8 or 16 bit integer
    """               
    if array.dtype == 'uint8':
        length = 256 
        offset = 0
    elif array.dtype == 'int8':
        length = 256
        offset = 128
    elif array.dtype == 'uint16':
        length = 65536
        offset = 0
    elif array.dtype == 'int16':
        length = 65536
        offset = 32768
    
    if array.dtype in ['uint8', 'uint16']:
        if use_numba and has_numba:
            hist = numba_func.bincount2d(array, length)    
        else:
            if use_numba:
                logger.warning('Numba is not available')
            hist = np.bincount(array.ravel(), minlength=length)
            
    elif array.dtype in ['int8', 'int16']:
        if array.dtype == 'int8':
            unsigned_array = array.view('uint8')
        else:
            unsigned_array = array.view('uint16')
        if use_numba and has_numba:
            hist = numba_func.bincount2d(unsigned_array, length)    
        else:
            if use_numba:
                logger.warning('Numba is not available')
            hist = np.bincount(unsigned_array.ravel(), minlength=length)        
                    
        hist = np.r_[hist[len(hist)//2:], hist[:len(hist)//2]]
    
    non_zeros_indices = np.argwhere(hist > 0)
    min_index = non_zeros_indices[0][0]
    max_index = non_zeros_indices[-1][0]
    
    first_edge = min_index if low is None else low  
    last_edge = max_index if high is None else high    

    if step is None:    
        if first_edge == last_edge:
            stepsize = max((last_edge - first_edge) / (bins-1), 1)
        else:
            stepsize = 1
    else:
        stepsize = step               
    
    stepsize = max(2**math.floor(np.log2(stepsize)), 1)    
    
    if stepsize > 1:
        hist = hist.reshape(length // stepsize, stepsize).sum(1)
        non_zeros_indices = np.argwhere(hist > 0)
        min_index = non_zeros_indices[0][0]
        max_index = non_zeros_indices[-1][0]
        first_edge = min_index
        last_edge = max_index
    
    starts = np.arange(first_edge, last_edge+1) * stepsize - offset
    
    return hist[min_index:max_index+1], starts, stepsize
    
def histfloat(array, bins=64, step=None, low=None, high=None, pow2snap=True, use_numba=True):

    if (low is None or high is None):
        if use_numba:
            minimum, maximum = numba_func.get_min_max(array)
        else:
            minimum, maximum = array.min(), array.max()
        
    first_edge = minimum if low is None else low    
    last_edge = maximum if high is None else high    

    if first_edge == last_edge:
        first_edge -= 0.5
        last_edge += 0.5
    
    if step is None:    
        stepsize = (last_edge - first_edge) / (bins-1)
    else:
        stepsize = step               
    
    if pow2snap:
        stepsize = 2**math.floor(np.log2(stepsize))
        bins = min(math.ceil((last_edge - first_edge) / stepsize), 65536)    
    
    starts = first_edge + np.arange(bins) * stepsize
    offset = first_edge
      
    if not len(starts) <= 65536:    
        logger.warning(f'To many bins {len(starts)} is larger then 65536')
        logger.warning(f'first_edge: {first_edge}; last_edge: {last_edge}; stepsize: {stepsize}')
        starts = starts[:65536]
    
    #TO DO, clipping is only needed if values are outside the bins
    #This means that minimum and maximum should always be calculated
    if (offset != 0) and (stepsize != 1):
        array16bit = ((array - offset) / stepsize).clip(0, 65535).astype('uint16') 
    elif (stepsize != 1):    
        array16bit = (array / stepsize).clip(0, 65535).astype('uint16') 
    elif (offset != 0):        
        array16bit = (array - offset).clip(0, 65535).astype('uint16') 
    else:
        array16bit = array.clip(0, 65535).astype('uint16')
    
    if use_numba and has_numba:
        hist = numba_func.bincount2d(array16bit, 65536)[:len(starts)] 
    else:
        hist = np.bincount2d(array16bit, minlength=65536)[:len(starts)]        
    
    return hist, starts, stepsize  
    
