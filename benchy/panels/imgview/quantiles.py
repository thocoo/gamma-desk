import numpy as np
from .fasthist import hist2d

stdquant = np.ndarray(13)
stdquant[0] = (0.0000316712418331200)  #-4 sdev
stdquant[1] = (0.0013498980316301000)  #-3 sdev
stdquant[2] = (0.0227501319481792000)  #-2 sdev
stdquant[3] = (0.05)
stdquant[4] = (0.1586552539314570000)  #-1 sdev or lsdev
stdquant[5] = (0.25)                   #first quartile
stdquant[6] = (0.50)                   #median
stdquant[7] = (0.75)                   #third quartile
stdquant[8] = (0.8413447460685430000)  #+1 sdev or usdev
stdquant[9] = (0.95)
stdquant[10] = (0.9772498680518210000) #+2 sdev
stdquant[11] = (0.9986501019683700000) #+3 sdev
stdquant[12] = (0.9999683287581670000) #+4 sdev
            

def get_standard_quantiles(arr, bins=64, step=None, quantiles=None):

    hist, starts, stepsize = hist2d(arr, bins, step, plot=False)              
    cumhist = np.cumsum(hist)       
    
    if quantiles is None:
        quantiles = stdquant  
    else:
        quantiles = np.array(quantiles)

    n = len(quantiles)
    npix = np.multiply.reduce(arr.shape)
    quantiles *= npix                                
    thresh = [0] * n
    
    #TO DO: speed up by using interpolation function of numpy
    for ind in range(n):
        thresh[ind] = starts[(cumhist < quantiles[ind]).sum()]
            
    return thresh
    
def get_sigma_range(arr, sigma=1, bins=64, step=None):    
    if sigma == 1:
        return get_standard_quantiles(arr, bins, step, (stdquant[4], stdquant[8])) 
    elif sigma == 2:
        return get_standard_quantiles(arr, bins, step, (stdquant[2], stdquant[10]))
    elif sigma == 3:
        return get_standard_quantiles(arr, bins, step, (stdquant[1], stdquant[11]))
    elif sigma == 4:
        return get_standard_quantiles(arr, bins, step, (stdquant[0], stdquant[12]))
        
        
def get_sigma_range_for_hist(starts, hist, sigma):
    cumhist = np.cumsum(hist)
    
    if sigma==1:
        quantiles = np.array((stdquant[4], stdquant[8]))
    elif sigma==2:
        quantiles = np.array((stdquant[2], stdquant[10]))
    elif sigma==3:
        quantiles = np.array((stdquant[1], stdquant[11]))
    elif sigma==4:
        quantiles = np.array((stdquant[0], stdquant[12]))               

    n = len(quantiles)
    npix = cumhist[-1]
    quantiles *= npix                                
    thresh = [0] * n
    
    #TO DO: speed up by using interpolation function of numpy
    for ind in range(n):
        thresh[ind] = starts[(cumhist < quantiles[ind]).sum()]
            
    return thresh    