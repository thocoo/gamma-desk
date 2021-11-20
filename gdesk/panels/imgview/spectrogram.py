import sys
import numpy as np

from ... import gui
    
def spectrogram(arr, vertical=False, plot=True):
    """
    Calculates the fullnoise, whitenoise and whiteness.
    and plot a spectrogram.
    
    https://www.emva.org/wp-content/uploads/EMVA1288-3.1a.pdf
    
    :param np.ndarray arr: A 2 dimensional array
    :param bool vertical: Calculate in vertical direction
    :param bool plot: Plot and print
    :returns: fullnoise, whitenoise, whiteness
    :rtype: tuple(float, float, float)
    """
    if vertical:
        return spectr_vert(arr, plot)
    else:
        return spectr_hori(arr, plot)
    
def spectr_hori(arr, plot=True):            
    """
    Calculates the fullnoise, whitenoise and whiteness.
    and plot a horizontal spectrogram.
    
    :param np.ndarray arr: A 2 dimensional array
    :returns: fullnoise, whitenoise, whiteness
    :rtype: tuple(float, float, float)    
    """
    arr = arr.astype('double')
    ydim, xdim = arr.shape
    arr -= arr.mean()
    mag = abs(np.fft.fft(arr,axis=1)) / xdim ** 0.5
    spr = (np.sum(mag**2,0) / ydim) ** 0.5
    fullnoise = (np.sum(spr**2) / (xdim+1))** 0.5
    whitenoise = np.median(spr)
    whiteness = (fullnoise / whitenoise)
    
    if plot:
        plt = gui.prepareplot()
        plt.figure()
        plt.grid(True)
        plt.title('Horizontal Spectrogram')
        plt.plot(spr)    
    
        print("Fullnoise    :  %8.2f" % fullnoise)
        print("WhiteNoise   :  %8.2f" % whitenoise)
        print("The whiteness:  %8.2f Ideal this is 1" % whiteness)
        
    plt.show()
    
    return fullnoise, whitenoise, whiteness
    
def spectr_vert(arr, plot=True): 
    """
    Calculates the fullnoise, whitenoise and whiteness.
    and plot a vertical spectrogram.
    
    :param np.ndarray arr: A 2 dimensional array
    :returns: fullnoise, whitenoise, whiteness
    :rtype: tuple(float, float, float)    
    """
    arr = arr.astype('double')
    ydim, xdim = arr.shape
    arr -= arr.mean()
    mag = abs(np.fft.fft(arr,axis=0)) / ydim ** 0.5
    spr = (np.sum(mag**2,1) / xdim) ** 0.5
    fullnoise = (np.sum(spr**2) / (ydim+1))** 0.5
    whitenoise = np.median(spr)
    whiteness = (fullnoise / whitenoise)
    
    if plot:
        plt = gui.prepareplot()
        plt.figure()
        plt.grid(True)
        plt.title('Vertical Spectrogram')
        plt.plot(spr)            
    
        print("Fullnoise    :  %8.2f" % fullnoise)
        print("WhiteNoise   :  %8.2f" % whitenoise)
        print("The whiteness:  %8.2f Ideal this is 1" % whiteness) 
        
    plt.show()
    
    return fullnoise, whitenoise, whiteness    