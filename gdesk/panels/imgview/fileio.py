import struct
from pathlib import Path

import numpy as np

from ... import gui
from .dialogs import RawImportDialog

try:
    import imageio
    HAS_IMAFIO = True

except:
    HAS_IMAFIO = False

HERE = Path(__file__).parent.absolute()


def import_raw_image():        

    filepath = HERE / 'images' / 'default.png'
    filepath = gui.getfile(file=str(filepath))[0]
    if filepath == '': return

    fp = open(filepath, 'br')
    data = fp.read()
    fp.close()

    #somehwhere in the header, there is the resolution
    #image studio: 128 bytes header, 4 bytes=width, 4 bytes=height, 120 bytes=???
    header = 128
    dtype = 'uint16'
    width = struct.unpack('<I', data[0:4])[0]
    height = struct.unpack('<I', data[4:8])[0]
    
    print(f'Width x Height: {width} x {height}')
            
    dialog = RawImportDialog(data)
    dialog.form.offset.setText(str(header))
    dialog.form.dtype.setText(dtype)
    dialog.form.width.setText(str(width))
    dialog.form.height.setText(str(height))
    dialog.exec_()
    
    offset = int(dialog.form.offset.text())
    dtype = dialog.form.dtype.text()
    byteorder = dialog.form.byteorder.currentText()
    width = int(dialog.form.width.text())
    height = int(dialog.form.height.text())


    with gui.qapp.waitCursor():
        dtype = np.dtype(dtype)

        leftover = len(data) - (width * height  * dtype.itemsize + offset)

        if leftover > 0:
            print('Too much data found (%d bytes too many)' % leftover)

        elif leftover < 0:
            print('Not enough data found (missing %d bytes)' % (-leftover))

        arr = np.ndarray(shape=(height, width), dtype=dtype, buffer=data[offset:])
        
        if byteorder == 'big endian':
            arr = arr.byteswap()            
        
        gui.qapp.history.storepath(str(filepath))
        
    return arr
    
    
def save_image_imafio(image, filepath, format):
    
    if format is None:
        from imageio.core import Request
        format = imageio.formats.search_write_format(Request(filepath, 'wi')).name        

    if format == 'JPEG-FI':
        (quality, progressive, optimize, baseline) = gui.fedit([('quality', 90), ('progressive', False), ('optimize', False), ('baseline', False)], title='JPEG Options')

        with gui.qapp.waitCursor(f'Saving to {filepath}'):
            imageio.imwrite(filepath, image, format,
                quality=quality, progressive=progressive,
                optimize=optimize, baseline=baseline)

    elif format == 'TIFF-FI':
        compression_options = {
            'none': imageio.plugins.freeimage.IO_FLAGS.TIFF_NONE,
            'default': imageio.plugins.freeimage.IO_FLAGS.TIFF_DEFAULT,
            'packbits': imageio.plugins.freeimage.IO_FLAGS.TIFF_PACKBITS,
            'adobe': imageio.plugins.freeimage.IO_FLAGS.TIFF_ADOBE_DEFLATE,
            'lzw': imageio.plugins.freeimage.IO_FLAGS.TIFF_LZW,
            'deflate': imageio.plugins.freeimage.IO_FLAGS.TIFF_DEFLATE,
            'logluv': imageio.plugins.freeimage.IO_FLAGS.TIFF_LOGLUV}
        (compression_index,) = gui.fedit([('compression', [2] + list(compression_options.keys()))], title='TIFF Options')
        compression = list(compression_options.keys())[compression_index-1]
        compression_flag = compression_options[compression]

        with gui.qapp.waitCursor(f'Saving to {filepath}'):
            imageio.imwrite(filepath, image, format, flags=compression_flag)            

    elif format == 'PNG-FI':
        compression_options = [('None', 0), ('Best Speed', 1), ('Default', 6), ('Best Compression', 9)]
        (compression_index, quantize, interlaced) = gui.fedit([('compression', [2] + [item[0] for item in compression_options]), ('quantize', 0), ('interlaced', True)], title='PNG Options')
        compression = compression_options[compression_index-1][1]

        print(f'compression: {compression}')

        with gui.qapp.waitCursor(f'Saving to {filepath}'):
            imageio.imwrite(filepath, image, format, compression=compression, quantize=quantize, interlaced=interlaced)

    elif format == 'PNG-PIL':
        compression_options = [('None', 0), ('Best Speed', 1), ('Default', 6), ('Best Compression', 9)]
        (compression_index, quantize, optimize) = gui.fedit([('compression', [4] + [item[0] for item in compression_options]), ('quantize', 0), ('optimize', True)], title='PNG Options')
        compression = compression_options[compression_index-1][1]
        if quantize == 0: quantize = None

        print(f'compression: {compression}')

        with gui.qapp.waitCursor(f'Saving to {filepath}'):
            imageio.imwrite(filepath, image, format, compression=compression,
                quantize=quantize, optimize=optimize, prefer_uint8=False)

    else:
        with gui.qapp.waitCursor(f'Saving to {filepath}'):
            imageio.imwrite(filepath, image, format)    
