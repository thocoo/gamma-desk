"""multiple dimension range and slicing

    virtual sequence of numbers defined by start to stop by step
    functions to
        * modify the range by applying slices
        * reset to full range
        * get default python range object
        * partial ranges for representations

    start = first number; 0 by default
    stop = all numbers are lower then stop, so not included in sequence
    step = stepping of the sequence; 1 by default
    maxstop = stop can never be set larger than maxstop

    DimRange: single dimension
    DimRanges: multiple dimensions
"""


class DimRange(object):
    """range info of a single dimension

    maxstop = the size of the dimension

    apply slices to a range to get a new range
    slices can be applied cumulatively
    range can be reset to the original range
    """
    def __init__(self, maxstop):
        self.maxstop = maxstop
        self.start = 0
        self.stop = maxstop
        self.step = 1

    def reset(self):
        self.start = 0
        self.stop = self.maxstop
        self.step = 1

    def clone(self):
        return DimRange(self.maxstop)

    def inherite(self, source):
        self.start = source.start
        self.stop = source.stop
        self.step = source.step

    def copy(self):
        result = self.clone()
        result.inherite(self)
        return result

    def setfromslice(self, aslice, full=True):
        """slice the current range by the slice aslice

        a slice is e.g. created from item[0:10:2]
            or by slice(0,10,2)

        if full == True: don't build on the current roi
        """
        if full:
            # reset the roi before the new roi
            self.reset()

        prior_start = self.start
        prior_stop = self.stop
        prior_step = self.step

        if isinstance(aslice, int):
            # the slice is just one index
            if aslice < 0:
                aslice = max(prior_stop + prior_step * aslice, 0)
            aslice = slice(aslice, aslice+1, None)

        if aslice.start is None:
                self.start = prior_start
        elif aslice.start < 0:
            self.start = max(prior_stop + prior_step * aslice.start, 0)
        else:
            self.start = min(prior_start + prior_step * aslice.start, prior_stop)

        if aslice.stop is None:
            self.stop = prior_stop
        elif aslice.stop < 0:
            self.stop = max(prior_stop + prior_step * aslice.stop, 0)
        else:
            self.stop = min(prior_start + prior_step * aslice.stop, prior_stop)

        if aslice.step is None:
            self.step = prior_step
        else:
            self.step = prior_step * aslice.step

    def applyslice(self, aslice, full=False):
        """return a range based on another range and a range definition

        ex:
           bslice = slice(3,None,2) or [3::2] on the __getitem__ or __setitem__
           brange = (0,50,2)
           return range(6,50,4)
        """
        self.setfromslice(aslice, full)

    def clip(self):
        if self.start < self.maxstop:
            self.start = max(self.start, 0)
        else:
            self.start = 0
        if self.stop > 0:
            self.stop = min(self.stop, self.maxstop)
        else:
            self.stop = self.maxstop
            
    def size(self):
        return len(self)

    def __len__(self):
        return len(self.range)

    def isfullrange(self):
        if (self.start == 0) and (self.stop == self.maxstop) and (self.step == 1):
            return True
        else:
            return False

    def getstartrange(self, count=7):
        half = count // 2
        if self.count > count:
            tmp = self.copy()
            tmp.applyslice(slice(None, half, None), False)  # 2nd argument unnecessary
            return tmp.getrange()
        else:
            return self.getrange()

    def getstoprange(self, count=7):
        half = count // 2
        if self.count > count:
            tmp = self.copy()
            if (tmp.stop - tmp.start) % tmp.step != 0:
                tmp.maxstop += tmp.step - (tmp.stop - tmp.start) % tmp.step
                tmp.stop = tmp.maxstop
            tmp.applyslice(slice(-half, None,  None), False)  # 2nd argument unnecessary
            return tmp.getrange()
        else:
            return None

    def __str__(self):
        return 'dim:%d slice:%d:%d:%d' % (self.maxstop, self.start, self.stop, self.step) 

    def __repr__(self):
        return str(self)

    def __getitem__(self, index):
        newrange = self.copy()
        newrange.applyslice(index, False)  # 2nd argument is unnecessary
        return newrange

    def getslice(self):
        return slice(self.start, self.stop, self.step)        
        
    def getrange(self):
        return range(self.start, self.stop, self.step)
        
    def splitstarts(self, count):
        from math import ceil
        l = len(self)
        step = ceil(l / count)
        return self.range[::step]

    count = property(size)
    slice = property(getslice)
    range = property(getrange)


class SetSlices(object):
    """
    to set the roi, use the slices syntax on set
    example:
        b = pybix.ones(100,80) * 12000
        b.roi
        >>>[dim:100 slice:0:100:1, dim:80 slice:0:80:1]
        b.roi.set[20:60,::2]
        b.roi
        >>>[dim:100 slice:20:60:1, dim:80 slice:0:80:2]            
    """
    def __init__(self, parent):
        self.parent = parent

    def __getitem__(self, indices):
        self.parent.setslices(indices)
        
    def __repr__(self):     
        return self.__doc__


class DimRanges(object):
    """range info of a multiple dimensions

    sizes = tuple of the sizes of the dimensions
    """
    def __init__(self, sizes=None):
        self.rngs = []
        self.set = SetSlices(self)
        if sizes is not None:
            for size in sizes:
                self.rngs.append(DimRange(size))

    def maketuple(self, index):
        if not isinstance(index, tuple):
            return (index,)
        else:
            return index

    def setslices(self, index):
        slices = self.maketuple(index)
        for i in range(len(self.rngs)):
            self.rngs[i].applyslice(slices[i], full=True)

    def accslices(self, index):
        slices = self.maketuple(index)
        for (rng, slc) in zip(self.rngs, slices):
            rng.applyslice(slc, full=False)

    def getslices(self, swap_row_columns=False):
        tmp = []        
        for rng in self.rngs:
            tmp.append(rng.getslice())
        if swap_row_columns:
            # swap first and second index
            tmp[0], tmp[1] = tmp[1], tmp[0]
        return tuple(tmp)

    def getshape(self):
        tmp = []
        for rng in self.rngs:
            tmp.append(len(rng))
        return tuple(tmp)        
    
    shape = property(getshape)
    
    def getfullshape(self):
        tmp = []
        for rng in self.rngs:
            tmp.append(rng.maxstop)
        return tuple(tmp)

    fullshape = property(getfullshape)

    def reset(self):
        for rng in self.rngs:
            rng.reset()

    def clip(self):
        for rng in self.rngs:
            rng.clip()

    def clone(self):
        return DimRanges(self.shape)

    def inherite(self, source):
        for (tarr, srcr) in zip(self.rngs, source.rngs):
            tarr.inherite(srcr)

    def copy(self):
        newrngs = self.clone()
        newrngs.inherite(self)
        return newrngs

    def isfullrange(self):
        test = True
        for rngs in self.rngs:
            test &= rngs.isfullrange()
        return test        

    def __len__(self):
        length = 1
        for rng in self.rngs:
            length *= len(rng)
        return length

    def __getitem__(self, indices):
        newranges = self.copy()
        newranges.accslices(indices)
        return newranges

    def __str__(self):
        return str(self.rngs)

    def __repr__(self):
        return str(self)
