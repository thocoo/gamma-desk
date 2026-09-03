import math

import numpy as np

from gdesk.panels.imgview import fasthist


class HistAgg(object):
    
    def __init__(self, channel):
        self.channel = channel
        self._cache = {}
        
        
    def clear(self):
        self._cache.clear()                            


    @property
    def roi(self):
        return self.channel.roi
        

    @property
    def dtype(self):
        return self.roi.dtype
        
        
    def n(self):
        return self.channel.n()
        
        
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
        if isinstance(self.roi, np.ma.MaskedArray):
            data = self.roi.compressed()
        else:
            data = self.roi
            
        if self.dtype in ['int8', 'uint8', 'int16', 'uint16']:
            hist, starts, stepsize = fasthist.hist16bit(data, bins=None, step=1, use_numba=True)
            
        elif self.dtype in ['int32', 'uint32', 'int64', 'uint64', 'float16', 'float32', 'float64']:
            hist, starts, stepsize = fasthist.histfloat(data, bins=65536, step=None, pow2snap=False, use_numba=True)
            
        self._cache['hist'] = hist
        self._cache['starts'] = starts
        self._cache['stepsize'] = stepsize    
    
    
    def step_for_bins(self, bins):
        if self.dtype in ['float16', 'float32', 'float64']:
            return math.ceil(65536 / bins) 
            
        if len(self._cache.keys()) == 0:
            self.calc_histogram()
            
        hist1 = self._cache['hist']  
        
        return math.ceil(len(hist1) / bins)  
        
    
    @property    
    def bins(self):
        return len(self.starts())
        
        
    def stepsize(self, step):
        return self._cache['stepsize'] * step
        

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