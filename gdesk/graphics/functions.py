import struct

import numpy as np

from qtpy import QtCore, QtGui

Colors = {
    'b': (0,0,255,255),
    'g': (0,255,0,255),
    'r': (255,0,0,255),
    'c': (0,255,255,255),
    'm': (255,0,255,255),
    'y': (255,255,0,255),
    'k': (0,0,0,255),
    'w': (255,255,255,255),
}

def intColor(index, hues=9, values=1, maxValue=255, minValue=150, maxHue=360, minHue=0, sat=255, alpha=255, **kargs):
    """
    Creates a QColor from a single index. Useful for stepping through a predefined list of colors.

    The argument *index* determines which color from the set will be returned. All other arguments determine what the set of predefined colors will be

    Colors are chosen by cycling across hues while varying the value (brightness).
    By default, this selects from a list of 9 hues."""
    hues = int(hues)
    values = int(values)
    ind = int(index) % (hues * values)
    indh = ind % hues
    indv = ind / hues
    if values > 1:
        v = minValue + indv * ((maxValue-minValue) / (values-1))
    else:
        v = maxValue
    h = minHue + (indh * (maxHue-minHue)) / hues

    c = QtGui.QColor()
    c.setHsv(h, sat, v)
    c.setAlpha(alpha)
    return c

def mkColor(*args):
    """
    Convenience function for constructing QColor from a variety of argument types. Accepted arguments are:

    ================ ================================================
     'c'             one of: r, g, b, c, m, y, k, w
     R, G, B, [A]    integers 0-255
     (R, G, B, [A])  tuple of integers 0-255
     float           greyscale, 0.0-1.0
     int             see :func:`intColor() <pyqtgraph.intColor>`
     (int, hues)     see :func:`intColor() <pyqtgraph.intColor>`
     "RGB"           hexadecimal strings; may begin with '#'
     "RGBA"
     "RRGGBB"
     "RRGGBBAA"
     QColor          QColor instance; makes a copy.
    ================ ================================================
    """
    err = 'Not sure how to make a color from "%s"' % str(args)
    if len(args) == 1:
        if isinstance(args[0], QtGui.QColor):
            return QtGui.QColor(args[0])
        elif isinstance(args[0], float):
            r = g = b = int(args[0] * 255)
            a = 255
        #elif isinstance(args[0], basestring):
        elif isinstance(args[0], str):
            c = args[0]
            if c[0] == '#':
                c = c[1:]
            if len(c) == 1:
                (r, g, b, a) = Colors[c]
            if len(c) == 3:
                r = int(c[0]*2, 16)
                g = int(c[1]*2, 16)
                b = int(c[2]*2, 16)
                a = 255
            elif len(c) == 4:
                r = int(c[0]*2, 16)
                g = int(c[1]*2, 16)
                b = int(c[2]*2, 16)
                a = int(c[3]*2, 16)
            elif len(c) == 6:
                r = int(c[0:2], 16)
                g = int(c[2:4], 16)
                b = int(c[4:6], 16)
                a = 255
            elif len(c) == 8:
                r = int(c[0:2], 16)
                g = int(c[2:4], 16)
                b = int(c[4:6], 16)
                a = int(c[6:8], 16)
        elif hasattr(args[0], '__len__'):
            if len(args[0]) == 3:
                (r, g, b) = args[0]
                a = 255
            elif len(args[0]) == 4:
                (r, g, b, a) = args[0]
            elif len(args[0]) == 2:
                return intColor(*args[0])
            else:
                raise Exception(err)
        elif type(args[0]) == int:
            return intColor(args[0])
        else:
            raise Exception(err)
    elif len(args) == 3:
        (r, g, b) = args
        a = 255
    elif len(args) == 4:
        (r, g, b, a) = args
    else:
        raise Exception(err)

    args = [r,g,b,a]
    #args = [0 if np.isnan(a) or np.isinf(a) else a for a in args]
    args = list(map(int, args))
    return QtGui.QColor(*args)

def mkBrush(*args, **kwds):
    """
    | Convenience function for constructing Brush.
    | This function always constructs a solid brush and accepts the same arguments as :func:`mkColor() <pyqtgraph.mkColor>`
    | Calling mkBrush(None) returns an invisible brush.
    """
    if 'color' in kwds:
        color = kwds['color']
    elif len(args) == 1:
        arg = args[0]
        if arg is None:
            return QtGui.QBrush(QtCore.Qt.NoBrush)
        elif isinstance(arg, QtGui.QBrush):
            return QtGui.QBrush(arg)
        else:
            color = arg
    elif len(args) > 1:
        color = args
    return QtGui.QBrush(mkColor(color))
    
def arrayToQPath(x, y, connect='all'):
    """Convert an array of x,y coordinats to QPainterPath as efficiently as possible.
    The *connect* argument may be 'all', indicating that each point should be
    connected to the next; 'pairs', indicating that each pair of points
    should be connected, or an array of int32 values (0 or 1) indicating
    connections.
    """
    
    #CODE IS COPIED FROM PYQTGRAPH

    ## Create all vertices in path. The method used below creates a binary format so that all
    ## vertices can be read in at once. This binary format may change in future versions of Qt,
    ## so the original (slower) method is left here for emergencies:
        #path.moveTo(x[0], y[0])
        #if connect == 'all':
            #for i in range(1, y.shape[0]):
                #path.lineTo(x[i], y[i])
        #elif connect == 'pairs':
            #for i in range(1, y.shape[0]):
                #if i%2 == 0:
                    #path.lineTo(x[i], y[i])
                #else:
                    #path.moveTo(x[i], y[i])
        #elif isinstance(connect, np.ndarray):
            #for i in range(1, y.shape[0]):
                #if connect[i] == 1:
                    #path.lineTo(x[i], y[i])
                #else:
                    #path.moveTo(x[i], y[i])
        #else:
            #raise Exception('connect argument must be "all", "pairs", or array')

    ## Speed this up using >> operator
    ## Format is:
    ##    numVerts(i4)   0(i4)
    ##    x(f8)   y(f8)   0(i4)    <-- 0 means this vertex does not connect
    ##    x(f8)   y(f8)   1(i4)    <-- 1 means this vertex connects to the previous vertex
    ##    ...
    ##    0(i4)
    ##
    ## All values are big endian--pack using struct.pack('>d') or struct.pack('>i')

    path = QtGui.QPainterPath()

    #profiler = debug.Profiler()
    n = x.shape[0]
    # create empty array, pad with extra space on either end
    arr = np.empty(n+2, dtype=[('x', '>f8'), ('y', '>f8'), ('c', '>i4')])
    # write first two integers
    #profiler('allocate empty')
    byteview = arr.view(dtype=np.ubyte)
    byteview[:12] = 0
    byteview.data[12:20] = struct.pack('>ii', n, 0)
    #profiler('pack header')
    # Fill array with vertex values
    arr[1:-1]['x'] = x
    arr[1:-1]['y'] = y

    # decide which points are connected by lines
    #I replaced eq function by ==
    if connect == 'all':
        arr[1:-1]['c'] = 1
    elif connect == 'pairs':
        arr[1:-1]['c'][::2] = 1
        arr[1:-1]['c'][1::2] = 0
    elif connect == 'finite':
        arr[1:-1]['c'] = np.isfinite(x) & np.isfinite(y)
    elif isinstance(connect, np.ndarray):
        arr[1:-1]['c'] = connect
    else:
        raise Exception('connect argument must be "all", "pairs", "finite", or array')

    #profiler('fill array')
    # write last 0
    lastInd = 20*(n+1)
    byteview.data[lastInd:lastInd+4] = struct.pack('>i', 0)
    #profiler('footer')
    # create datastream object and stream into path

    ## Avoiding this method because QByteArray(str) leaks memory in PySide
    #buf = QtCore.QByteArray(arr.data[12:lastInd+4])  # I think one unnecessary copy happens here

    path.strn = byteview.data[12:lastInd+4] # make sure data doesn't run away
    try:
        buf = QtCore.QByteArray.fromRawData(path.strn)
    except (TypeError, AttributeError):
        buf = QtCore.QByteArray(bytes(path.strn))
    #profiler('create buffer')
    ds = QtCore.QDataStream(buf)

    ds >> path
    #profiler('load')

    return path    