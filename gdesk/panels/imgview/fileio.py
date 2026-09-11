import logging
import collections
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np

from ... import gui, config
from .dialogs import RawImportDialog

try:
    import imageio
    HAS_IMAFIO = True

except:
    HAS_IMAFIO = False
    
from PIL import Image as PilImage

HERE = Path(__file__).parent.absolute()

if HAS_IMAFIO:
    try:
        if not config.get("path_imageio_freeimage_lib", None) is None:
            if os.getenv("IMAGEIO_FREEIMAGE_LIB", None) is None:
                os.environ["IMAGEIO_FREEIMAGE_LIB"] = config.get("path_imageio_freeimage_lib")

        try:
            import imageio.plugins.freeimage
            imageio.plugins._freeimage.get_freeimage_lib()

        except Exception as ex:
            logger.warning('Could not load freeimage dll')
            logger.warning(str(ex))

        try:
            imageio.plugins.freeimage.download()

        except Exception as ex:
            logger.warning('Downloading imageio dll failed')
            logger.warning(str(ex))
            logger.warning('Automatic download can be a problem when using VPN')
            logger.warning("Download the dll's from https://github.com/imageio/imageio-binaries/tree/master/freeimage/")
            logger.warning(f'And place it in {imageio.core.appdata_dir("imageio")}/freeimage')

            #You can also use a system environmental variable
            #IMAGEIO_FREEIMAGE_LIB=<the location>\FreeImage-3.18.0-win64.dll

        #The effective dll is refered at
        #imageio.plugins.freeimage.fi.lib

        #Prefer freeimage above pil
        #Freeimage seems to be a lot faster then pil
        imageio.formats.sort('-FI', '-PIL')

        FILTERS_NAMES = collections.OrderedDict()
        FILTERS_NAMES['All Formats (*)'] = None

        for fmt in imageio.formats:
            filter = f'{fmt.name} - {fmt.description} (' + ' '.join(f'*{fmt}' for fmt in fmt.extensions) + ')'
            FILTERS_NAMES[filter] = fmt.name

        IMAFIO_QT_READ_FILTERS = ';;'.join(FILTERS_NAMES.keys())
        IMAFIO_QT_WRITE_FILTERS = ';;'.join(FILTERS_NAMES.keys())
        IMAFIO_QT_WRITE_FILTER_DEFAULT = "TIFF-FI - Tagged Image File Format (*.tif *.tiff)"

    except Exception as ex:
        logger.warning('Could not initialize imageio format filters, falling back to PIL save/open dialogs')
        logger.warning(str(ex))
        HAS_IMAFIO = False


def open_image(filepath, format=None):
    
    if not Path(filepath).exists():
        gui.msgbox(f'{filepath} not found.', title='File not found', icon='error')
        return        
        
    if HAS_IMAFIO:
        arr = open_image_imafio(filepath, format)
        
    else:        
        arr = open_image_pil(filepath)

    return arr    
    

def open_image_imafio(filepath, format=None):
    
    with gui.qapp.waitCursor(f'Opening image using imageio {filepath} {format}'):
        logger.info(f"Using FormatClass {repr(imageio.imopen(filepath, 'r').__class__)}")
        arr = imageio.imread(str(filepath), format=format)
        
    return arr
    
    
def open_image_pil(filepath):
    
    with gui.qapp.waitCursor(f'Opening image using PIL {filepath}'):        
        logger.info(f'Using PIL library')
        image = PilImage.open(str(filepath))
        arr = np.array(image)
        
    return arr    


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
    
    
def save_image_dialog(self):
    
    if HAS_IMAFIO:
        filepath, filter = gui.putfile(filter=IMAFIO_QT_WRITE_FILTERS, title='Save Image using Imafio',
                                defaultfilter=IMAFIO_QT_WRITE_FILTER_DEFAULT)
        if filepath == '': return
        format = FILTERS_NAMES[filter]
        save_image(filepath, format)
        
    else:
        filepath, filter = gui.putfile(title='Save Image using PIL')
        if filepath == '': return
        save_image(filepath)
        

def save_image(self, filepath, format=None):
    
    if HAS_IMAFIO:
        save_image_imafio(self.ndarray, filepath, format)
        
    else:
        save_image_pil(self.ndarray,  filepath)

    gui.qapp.history.storepath(str(filepath))    
    
    
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


def save_image_pil(image, filepath):
    
    with gui.qapp.waitCursor():
        
        image = PilImage.fromarray(self.ndarray)
        image.save(str(filepath))                 
