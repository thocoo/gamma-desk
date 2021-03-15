import numpy
import time 
import math

HFG = 8
USEFORDER = True
XKERN = 8
YKERN = 8

def make_thumbnail(array, max_long_side=240, hfg=HFG, bayer=False):

    if hasattr(array, 'tondarray'):
        array = image.tondarray('uint16')  # reference to uint16 buffer of Bindex 

    height, width = array.shape
    long_side = max(height, width)
    ratio = math.ceil(long_side / max_long_side)

    thumb = make_blueprint(array, ratio, ratio, hfg, bayer)
    return thumb
    
def get_blue_print(array, xkern=XKERN, ykern=YKERN, hfg=HFG, bayer=False):
    return make_blueprint(array, xkern, ykern, hfg, bayer)

def make_blueprint(array, xkern=XKERN, ykern=YKERN, hfg=HFG, bayer=False):
    """
    Make a so called blueprint thumbnail.
    The 16-bitgrey image is converted to a downscaled color version.
    The downscale kernel is tyical 8x8. So the statiscs of 64 pixels is used
    to derive 3 8-bit numbers. So the RGB values are based on the average,
    the minimum and the maximum.
    Green for the average of the kernel.
    Blue for the difference of the minumum to average.
    Red for the difference of maximum to average.
    The min-max differences are typical gained up.
    The final result is an image of 1/100 of the original data.
    It blows-up high frequency artifacts, making them much more visible.
    
    :param array: A 2d Image
    :type array: np.ndarray or PyBix
    :param int xkern: width of the kernel
    :param int ykern: height of the kernel
    :param float hfg: high frequency gain        
    :param bool bayer: Does it contains a bayer pattern (color sensor?)
    """

    def get_blue_print_of_roi(array, xkern, ykern, hfg):
        #the shape of array is supposed to be a multiple of xkern and ykern
        
        ydim, xdim = array.shape
        xdimsc = xdim // xkern
        ydimsc = ydim // ykern
        
        #note that a reshape doesn't realy do anything on the memory buffer
        #it only redefines the strides
        tmp2 = array.reshape(ydim * xdimsc, xkern)
        
        #calculates on every xkern succesive pixels in a row
        #total size of the array will be 8 times less
        min3 = tmp2.min(1)
        mean3 = tmp2.mean(1)
        max3 = tmp2.max(1)    
        
        #reshufle the memory
        #the copy is needed to really remap the memory
        if USEFORDER == False:
            #swap row and column in memory
            min4 = min3.reshape(ydim, xdimsc).T.copy()
            mean4 = mean3.reshape(ydim, xdimsc).T.copy()
            max4 = max3.reshape(ydim, xdimsc).T.copy()   
        
            min5 = min4.reshape(xdimsc * ydimsc, ykern)
            mean5 = mean4.reshape(xdimsc * ydimsc, ykern)
            max5 = max4.reshape(xdimsc * ydimsc, ykern)
            
            stataxis = 1
                    
        else:
            #the use or order='F' actual makes a copy
            #so we don't gain anything with this Fortran order
            min5 = min3.reshape(ydim, xdimsc).reshape(ykern, xdimsc * ydimsc, order='F')
            mean5 = mean3.reshape(ydim, xdimsc).reshape(ykern, xdimsc * ydimsc, order='F')
            max5 = max3.reshape(ydim, xdimsc).reshape(ykern, xdimsc * ydimsc, order='F')
            
            stataxis = 0
            
        #calculates on every 8 succesive pixels in a col
        #total size of the array will be now 64 times less then the orginal
        min6 = min5.min(stataxis)
        mean6 = mean5.mean(stataxis)
        max6 = max5.max(stataxis)        
            
        blueprint = numpy.ndarray((ydimsc, xdimsc, 3),'uint8')    
        
        if array.dtype == 'uint8':
            scale = 1
        elif array.dtype == 'uint16':
            scale = 256
            
        min7 = min6.reshape(xdimsc, ydimsc).T[:,:] // scale
        mean7 = mean6.reshape(xdimsc, ydimsc).T[:,:] // scale
        max7 = max6.reshape(xdimsc, ydimsc).T[:,:] // scale     
        
        blueprint[:,:,2] = (255 - (mean7 - min7) * hfg).clip(0,255)
        blueprint[:,:,1] = mean7
        blueprint[:,:,0] = ((max7 - mean7) * hfg).clip(0,255)
        
        #print("it took %8.2f seconds " % (time.time() - timestamp))
        return blueprint
        
    def blue_reduce_mono(array, kernel_width, kernel_height, hfgain):
        """
        array is supposed to be debayered
        """
    
        ydim, xdim = array.shape
    
        #round down and up to multiple of kernel widths and height
        xroundlow, xroundhigh = xdim // kernel_width * kernel_width, -(-xdim // kernel_width * kernel_width)
        yroundlow, yroundhigh = ydim // kernel_height * kernel_height, -(-ydim // kernel_height * kernel_height)
    
        if xroundlow == xroundhigh and yroundlow == yroundhigh:
            blue_print =  get_blue_print_of_roi(array, kernel_width, kernel_height, hfgain)
            
        else:
            xdimsc = xroundlow // xkern
            ydimsc = yroundlow // ykern
            if xroundlow == xroundhigh:          
                blue_print = numpy.ndarray((ydimsc+1, xdimsc, 3),'uint8')
                blue_print[:ydimsc,:] =  get_blue_print_of_roi(array[:yroundlow, :], xkern, ykern, hfgain)
                blue_print[ydimsc:,:] =  get_blue_print_of_roi(array[yroundlow:, :], xkern, ydim-yroundlow, hfgain)
            elif yroundlow == yroundhigh:
                blue_print = numpy.ndarray((ydimsc, xdimsc+1, 3),'uint8')
                blue_print[:, :xdimsc] =  get_blue_print_of_roi(array[:, :xroundlow], xkern, ykern, hfgain)
                blue_print[:, xdimsc:] =  get_blue_print_of_roi(array[:, xroundlow:], xdim-xroundlow, ykern, hfgain)        
            else:
                blue_print = numpy.ndarray((ydimsc+1, xdimsc+1, 3),'uint8')
                blue_print[:ydimsc, :xdimsc] =  get_blue_print_of_roi(array[:yroundlow, :xroundlow], xkern, ykern, hfgain)
                blue_print[:ydimsc, xdimsc:] =  get_blue_print_of_roi(array[:yroundlow, xroundlow:], xdim-xroundlow, ykern, hfgain)
                blue_print[ydimsc:, :xdimsc] =  get_blue_print_of_roi(array[yroundlow:, :xroundlow], xkern, ydim-yroundlow, hfgain)
                blue_print[ydimsc:, xdimsc:] =  get_blue_print_of_roi(array[yroundlow:, xroundlow:], xdim-xroundlow, ydim-yroundlow, hfgain)            
                
        return blue_print

    if hasattr(array, 'tondarray'):
        array = image.tondarray('uint16')  # reference to uint16 buffer of Bindex            
        
    if not len(array.shape) == 2:
        raise AttributeError('Only images with 1 channel (mono) is supported')
            
    if not bayer:
        blue_print = blue_reduce_mono(array, xkern, ykern, hfg)
        
    else:
        blue_prints = []
        for i,j in ((0,0),(1,0),(0,1),(1,1)):
            blue_prints.append(blue_reduce_mono(array[i::2,j::2], xkern, ykern, hfg))
            
        blue_print_width = blue_prints[0].shape[1] + blue_prints[2].shape[1]
        blue_print_height = blue_prints[0].shape[0] + blue_prints[1].shape[0]
        blue_print = numpy.zeros((blue_print_height, blue_print_width, 3), 'uint8')
        
        substarts = [(0,0),(1,0),(0,1),(1,1)]
        for i, sub_blue_print in enumerate(blue_prints):
            j, k = substarts[i]
            blue_print[j::2,k::2] = sub_blue_print
            
    return blue_print