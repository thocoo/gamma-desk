import numpy as np

def getOptimalMinimumSpacing(minVal, maxVal, scale=1):
    dif = abs(maxVal - minVal)
    if dif == 0:
        return 0
    size = dif * scale
    # decide optimal minor tick spacing in pixels (this is just aesthetics)
    pixelSpacing = np.log(size+10) * 5
    #pixelSpacing = np.log(size+10) * 2
    optimalTickCount = size / pixelSpacing
    if optimalTickCount < 1:
        optimalTickCount = 1
    # optimal minor tick spacing 
    minimumSpacing = dif / optimalTickCount  
    return minimumSpacing * scale

def tickSpacing(minimumSpacing=1, noDecimals=False):
    """Return values describing the desired spacing and offset of ticks.
    
    This method is called whenever the axis needs to be redrawn and is a 
    good method to override in subclasses that require control over tick locations.
    
    The return value must be a list of three tuples::
    
        [
            (major tick spacing, offset),
            (minor tick spacing, offset),
            (micro tick spacing, offset),
            ...
        ]
    """
    
    # the largest power-of-10 spacing which is smaller than optimal
    p10unit = 10 ** np.floor(np.log10(minimumSpacing))
    
    if noDecimals and p10unit < 1:
        return [5, 1, 1]
        # (5, 0),
        # (1, 0),
        # (1, 0)
        # ]  
        
    microInternals = np.array([0.2, 0.4, 1., 2.]) * p10unit
    minorInternals = np.array([1., 2., 5., 10.]) * p10unit
    majorInternals = np.array([2., 4., 10., 20.]) * p10unit        
        
        
    # Determine major/minor tick spacings which flank the optimal spacing.
    minorIndex = 3
    while minorInternals[minorIndex-1] > minimumSpacing:
        minorIndex -= 1

    # return [
        # (majorInternals[minorIndex], 0),
        # (minorInternals[minorIndex], 0),
        # (microInternals[minorIndex], 0)]
        
    return [majorInternals[minorIndex], minorInternals[minorIndex], microInternals[minorIndex]]    


def tickValues(minVal, maxVal, scale, minimumSpacing=None, noDecimals=False):
    """
    Return the values and spacing of ticks to draw::
    
        [  
            (spacing, [major ticks]), 
            (spacing, [minor ticks]), 
            ... 
        ]
    
    By default, this method calls tickSpacing to determine the correct tick locations.
    This is a good method to override in subclasses.
    """
    minVal, maxVal = sorted((minVal, maxVal))
    
    if minimumSpacing == None:
        minimumSpacing = getOptimalMinimumSpacing(minVal, maxVal, scale)
                
    ticks = []
    tickLevels = tickSpacing(minimumSpacing / scale, noDecimals)
    allValues = np.array([])
    # for i in range(len(tickLevels)):
        # spacing, offset = tickLevels[i]
    offset = 0
    for spacing in tickLevels:        
        # determine starting tick
        start = (np.ceil((minVal-offset) / spacing) * spacing) + offset
        
        # determine number of ticks
        num = int((maxVal-start) / spacing) + 1
        values = np.arange(num) * spacing + start
        # remove any ticks that were present in higher levels
        # we assume here that if the difference between a tick value and a previously seen tick value
        # is less than spacing/100, then they are 'equal' and we can ignore the new tick.
        values = list(filter(lambda x: all(np.abs(allValues-x) > spacing*0.01), values) )
        allValues = np.concatenate([allValues, values])
        scaledSpacing = spacing * scale
        ticks.append((scaledSpacing, values))        
        
    return ticks


class Ticks:

    def __init__(self, minVal, maxVal, scale, minimumSpacing=None, noDecimals=False):
        if minimumSpacing == None:
            self.minimumSpacing = getOptimalMinimumSpacing(minVal, maxVal, scale)
        else:
            self.minimumSpacing = minimumSpacing
        self.noDecimals = noDecimals
        
        self.values = []
        self.pop_values = []  #to be removed from scene
        self.push_values = [] #to be added to scene
        
        self.update(minVal, maxVal, scale)                       
        
    def update(self, minVal, maxVal, scale):
        self.spacings = tickSpacing(self.minimumSpacing / scale, self.noDecimals)
        
        values = []
        self.pop_values = []  #to be removed from scene
        self.push_values = [] #to be added to scene
        
        allValues = np.array([])
        #for i in range(len(self.tickLevels)):
        for spacing in self.spacings:
            #spacing, offset = self.tickLevels[i]
            
            # determine starting tick
            start = np.ceil(minVal / spacing)
            
            # determine number of ticks
            end = np.floor(maxVal / spacing) + 1
            
            val = np.arange(start, end) * spacing
            
            # remove any ticks that were present in higher levels
            # we assume here that if the difference between a tick value and a previously seen tick value
            # is less than spacing/100, then they are 'equal' and we can ignore the new tick.
            val = list(filter(lambda x: all(np.abs(allValues-x) > spacing*0.01), val) )
            allValues = np.concatenate([allValues, val])
            scaledSpacing = spacing * scale
            values.append((scaledSpacing, val))  
            
        if self.values != []:       
            for i in range(len(values)):            
                old_scaled_spacing, old_values = self.values[i]
                new_scaled_spacing, new_values = values[i]
                push_mask = np.in1d(new_values, old_values, invert = True)
                pop_mask = np.in1d(old_values, new_values, invert = True)
                self.push_values.append(np.array(new_values)[push_mask])
                self.pop_values.append(np.array(old_values)[pop_mask])
        else:
            self.push_values.append(values[0][1])
            self.push_values.append(values[1][1])
            self.push_values.append(values[2][1])
            
        # if len(self.push_values) != 0:
            # print('push', self.push_values)
        
        # if len(self.pop_values) != 0:
            # print('pop', self.pop_values)            
        
        self.values = values
