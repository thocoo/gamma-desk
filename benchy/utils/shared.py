#
# SharedArray can be initialized in Parent or Child process
# Uses anonymous mmap with tagnames
# A SharedArray can be send of multiprocessing queues
# Pickles only the mmap, tagname, sizes, ... but not the buffer.

import numpy as np
import os, time

import mmap, _winapi
import tempfile
        

class SharedArray:
    """
    Using shared memory.
    If pickled to another process, the memory is not copied.
    """
    
    #part of code copied from multiprocessing.heap module
    
    _rand = tempfile._RandomNameSequence()

    def __init__(self, shape, dtype=float):
        #convert dtype string to real dtype
        self.dtype = np.dtype(dtype)
        self.shape = shape
        for i in range(100):
            name = 'pym-%d-%s' % (os.getpid(), next(self._rand))
            buf = mmap.mmap(-1, self.bytesize, name)
            if _winapi.GetLastError() == 0:
                break
            # We have reopened a preexisting mmap.
            buf.close()
        else:
            raise FileExistsError('Cannot find name for new mmap')
        self.name = name   
        self._ndarray = None
        self._bindex = None
        self.base = buf
                        
    @staticmethod
    def from_ndarray(array):
        sa =  SharedArray(array.shape, array.dtype)
        sa.ndarray[:] = array
        return sa        
        
    @property
    def size(self):
         return np.multiply.reduce(self.shape, dtype='int64')
    
    @property    
    def ndim(self):
        return len(self.shape)
         
    @property
    def bytesize(self):
         return self.size * self.dtype.itemsize

    def __getstate__(self):
        return (self.name, self.dtype, self.shape)
        
    def __setstate__(self, state):    
        self.name, self.dtype, self.shape = self._state = state             
        self.base = mmap.mmap(-1, self.bytesize, self.name)
        assert _winapi.GetLastError() == _winapi.ERROR_ALREADY_EXISTS
        self._ndarray = None
        
    def _as_ndarray(self):
        arr = np.frombuffer(self.base, self.dtype, self.size).reshape(self.shape)
        return arr
        
    @property
    def ndarray(self):
        if self._ndarray is None:
            self._ndarray = self._as_ndarray()
        return self._ndarray        
            
    def __getitem__(self, slices):
        return self.ndarray.__getitem__(slices)
        
    def __setitem__(self, slices, other):
        return self.ndarray.__setitem__(slices, other)    
            
    def __str__(self):
        return self.ndarray.__str__()
            
    def __repr__(self):
        s = self.ndarray.__repr__()
        s = s.replace('array', 'SharedArray')
        return s
        
    def __dir__(self):
        d = dir(self.ndarray)
        d.extend(self.__dict__.keys())
        return d
        
    def __getattr__(self, attr):
        return getattr(self.ndarray, attr)
        
            