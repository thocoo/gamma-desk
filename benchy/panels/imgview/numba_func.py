import numpy as np
import numba

@numba.njit(cache=True)
def bincount2d(array, minlength=65536):          
    hist = np.bincount(array.ravel(), minlength=minlength)        
    return hist

@numba.njit(parallel=True, cache=True)    
def map_values_mono(source, target, mapvector):
    length = len(source)
    for i in numba.prange(length):
        value = source[i]
        target[i] = mapvector[value]
        
@numba.njit(parallel=True, cache=True)    
def map_values_rgb(source, target, mapvector):
    height, width, channels = source.shape
    for i in numba.prange(height):
        for j in numba.prange(width):
            target[i,j,0] = mapvector[source[i,j,0]]        
            target[i,j,1] = mapvector[source[i,j,1]]        
            target[i,j,2] = mapvector[source[i,j,2]]        
        
@numba.njit(parallel=True, cache=True)    
def map_values_rgbswap(source, target, mapvector):
    height, width, channels = source.shape
    for i in numba.prange(height):
        for j in numba.prange(width):
            target[i,j,2] = mapvector[source[i,j,0]]        
            target[i,j,1] = mapvector[source[i,j,1]]        
            target[i,j,0] = mapvector[source[i,j,2]]        
            target[i,j,3] = 255
            
@numba.njit(parallel=True, cache=True)    
def get_min_max(source):
    return source.min(), source.max()

def nb_float_offset_gain_gamma_8bit(array, offset=0, gain=1, gamma=1):
    procarr = np.ndarray(array.shape, 'uint8')
    nb_float_offset_gain_gamma_loop(array, procarr, offset, gain, gamma * 1.0)
    return procarr
    
@numba.njit(parallel=True, cache=True)     
def nb_float_offset_gain_gamma_loop(source, target, offset=0, gain=1, gamma=1):        
    height, width = source.shape
    gscale = 255 ** (1 - gamma)
    
    for i in numba.prange(height):
        for j in numba.prange(width):
            tmp = (source[i,j] - offset) * (gain * 256)
            if gamma == 1.0:
                if tmp < 0:
                    target[i,j] = 0
                elif tmp > 255:
                    target[i,j] = 255
                else:
                    target[i,j] = tmp
            else:
                tmp2 = tmp ** gamma * gscale
                if tmp2 < 0:
                    target[i,j] = 0
                elif tmp2 > 255:
                    target[i,j] = 255
                else:
                    target[i,j] = tmp2