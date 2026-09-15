import logging
import collections
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np

from ... import gui, config
from ...gcore.utils import ActionArguments
from .dialogs import RawImportDialog

from qtpy import QtCore, QtGui
from qtpy.QtWidgets import QAction, QMenu, QColorDialog, QApplication

from ...panels import CheckMenu
from ...dialogs.formlayout import fedit

from ... import config, gui

RESPATH = Path(config['respath'])


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
        

class OpenImage(object):
    def __init__(self, imgpanel, path):
        self.imgpanel = imgpanel
        self.path = path

    def __call__(self):
        self.imgpanel.openImage(self.path)
        

class RecentMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__('Recent', parent)
        self.imgpanel = self.parent()
        self.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'images.png')))
        self.aboutToShow.connect(self.initactions)


    def initactions(self):
        self.clear()
        self.actions = []

        for rowid, timestamp, path in gui.qapp.history.yield_recent_paths():
            action = QAction(path, self)
            action.triggered.connect(OpenImage(self.imgpanel, path))
            self.addAction(action)
            self.actions.append(action)
            

class FileMenu(CheckMenu):
    
    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)    
        
        self.basePanel = basePanel
        
        basePanel.addMenuItem(self, 'New...', self.newImage, icon='picture_empty.png',
            statusTip="Make a new image in this image viewer")
            
        basePanel.addMenuItem(self, 'Duplicate'         , self.basePanel.duplicate,
            statusTip="Duplicate the image to a new image viewer",
            icon = 'application_double.png')
        basePanel.addMenuItem(self, 'Open Image...' , self.openImageDialog,
            statusTip="Open an image",
            icon = 'folder_image.png')
        basePanel.addMenuItem(self, 'Import Raw Image...', self.importRawImage,
            statusTip="Import Raw Image",
            icon = 'picture_go.png')
            
        self.addMenu(RecentMenu(self))
        
        basePanel.addMenuItem(self, 'Save Image...' , self.saveImageDialog,
            statusTip="Save the image",
            icon = 'picture_save.png')
            
        basePanel.addMenuItem(self, 'Send to other GDesk' , self.send_array_to_gdesk)
            
        basePanel.addMenuItem(self, 'Close' , self.basePanel.close_panel,
            statusTip="Close this image panel",
            icon = 'cross.png') 


    @property
    def ndarray(self):
        return self.basePanel.ndarray

        
    def show_array(self, array, zoomFitHist=False, log=True, skip_init=False):
        self.basePanel.show_array(array, zoomFitHist, log, skip_init)                       
            
            
    def newImage(self):

        with ActionArguments(self) as args:
            args['width'] = 1920*2
            args['height'] = 1080*2
            args['channels'] = 1
            args['dtype'] = 'uint8'
            args['mean'] = 128

        if args.isNotSet():
            dtypes = ['uint8', 'int8', 'uint16', 'int16', 'uint32', 'int32', 'float32', 'float64']

            options_form = [('Width', args['width']),
                       ('Height', args['height']),
                       ('Channels', args['channels']),
                       ('dtype', [1] + dtypes),
                       ('mean', args['mean'])]

            result = fedit(options_form, title='New Image')
            if result is None: return
            args['width'], args['height'], args['channels'], dtype_ind, args['mean'] = result
            args['dtype'] = dtypes[dtype_ind-1]

        shape = [args['height'], args['width']]
        if args['channels'] > 1: shape = shape + [args['channels']]

        arr = np.ndarray(shape, args['dtype'])
        arr[:] = args['mean']

        self.show_array(arr, zoomFitHist=True)                                
        
        
    def openImageDialog(self):
        filepath = HERE / 'images' / 'default.png'

        with ActionArguments(self) as args:
            args['filepath'] = HERE / 'images' / 'default.png'
            args['format'] = None

        if args.isNotSet():
            if HAS_IMAFIO:
                args['filepath'], filter = gui.getfile(filter=IMAFIO_QT_READ_FILTERS, title='Open Image File (Imafio)', file=str(args['filepath']))
                if args['filepath'] == '': return
                args['format'] = FILTERS_NAMES[filter]

            else:
                args['filepath'], filter = gui.getfile(title='Open Image File (PIL)', file=str(args['filepath']))
                args['format'] = None
                if args['filepath'] == '': return

        self.openImage(args['filepath'], args['format'])


    def openImage(self, filepath, format=None, zoom='full'):
        
        if not Path(filepath).exists():
            gui.msgbox(f'{filepath} not found.', title='File not found', icon='error')
            return            
            
        if not Path(filepath).exists():
            gui.msgbox(f'{filepath} not found.', title='File not found', icon='error')
            return        
            
        if HAS_IMAFIO:
            image = self.open_image_imafio(filepath, format)
            
        else:        
            image = self.open_image_pil(filepath)
        
        if image is None: return

        gui.qapp.history.storepath(str(filepath))        
            
        self.show_array(image, zoomFitHist=True)
        
        if zoom == 'full':
            self.basePanel.viewMenu.zoomFull()
            
        else:
            self.basePanel.viewMenu.setZoomValue(zoom)         

        #self.basePanel.viewMenu.defaultOffsetGain()
        self.basePanel.viewMenu.gainToMinMax()                      


    def open_image_imafio(self, filepath, format=None):
        
        with gui.qapp.waitCursor(f'Opening image using imageio {filepath} {format}'):
            logger.info(f"Using FormatClass {repr(imageio.imopen(filepath, 'r').__class__)}")
            arr = imageio.imread(str(filepath), format=format)
            
        return arr
        
        
    def open_image_pil(self, filepath):
        
        with gui.qapp.waitCursor(f'Opening image using PIL {filepath}'):        
            logger.info(f'Using PIL library')
            image = PilImage.open(str(filepath))
            arr = np.array(image)
            
        return arr         
    

    def importRawImage(self):

        with ActionArguments(self) as args:
            args['filepath'] = 'image.png'
            args['offset'] = 128
            args['width'] = 1920
            args['height'] = 1080
            args['dtype'] = 'uint8'
            args['byteorder'] = 'litle endian'

        if args.isNotSet():
            filepath = HERE / 'images' / 'default.png'
            filepath = gui.getfile(file=str(filepath))[0]
            if filepath == '': return

        else:
            filepath = args['filepath'] 

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

        if args.isNotSet():                
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

        else:
            offset = args['offset']
            width = args['width']
            height = args['height']
            dtype = args['dtype']
            byteorder = args['byteorder']

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

        self.show_array(arr, zoomFitHist=True)
        self.basePanel.viewMenu.zoomFull()
        self.basePanel.viewMenu.gainToMinMax()
            

    def saveImageDialog(self):

        with ActionArguments(self) as args:
            args['filepath'] = 'image.png'
            args['format'] = None
            args['options'] = None
        
        if HAS_IMAFIO:
            if args.isNotSet():
                filepath, filter = gui.putfile(filter=IMAFIO_QT_WRITE_FILTERS, title='Save Image using Imafio',
                                        defaultfilter=IMAFIO_QT_WRITE_FILTER_DEFAULT)
                if filepath == '': return
                format = FILTERS_NAMES[filter]

            else:
                filepath = args['filepath']
                format = args['format']

            self.save_image(filepath, format, args['options'])
                
        else:
            if args.isNotSet():
                filepath, filter = gui.putfile(title='Save Image using PIL')
                if filepath == '': return
            else:
                filepath = args['filepath']
            self.save_image(filepath)
            
            
    def save_image(self, filepath, format=None, options=None):
        
        if HAS_IMAFIO:
            self.save_image_imafio(self.ndarray, filepath, format, options)
            
        else:
            save_image_pil(self.ndarray,  filepath)

        gui.qapp.history.storepath(str(filepath))       


    def save_image_imafio(self, image, filepath, format, options=None):
        
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
            if options is None:
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
            else:
                compression = options.get('compression', 'default')

            compression_flag = compression_options[compression]

            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, image, format, flags=compression_flag)            

        elif format == 'PNG-FI':
            if options is None:
                compression_options = [('None', 0), ('Best Speed', 1), ('Default', 6), ('Best Compression', 9)]
                (compression_index, quantize, interlaced) = gui.fedit([('compression', [2] + [item[0] for item in compression_options]), ('quantize', 0), ('interlaced', True)], title='PNG Options')
                compression = compression_options[compression_index-1][1]
            else:
                compression = options.get('compression', 6)
                quantize = options.get('quantize', 0)
                interlaced = options.get('interlaced', True)

            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, image, format, compression=compression, quantize=quantize, interlaced=interlaced)

        elif format == 'PNG-PIL':
            if options is None:
                compression_options = [('None', 0), ('Best Speed', 1), ('Default', 6), ('Best Compression', 9)]
                (compression_index, quantize, optimize) = gui.fedit([('compression', [4] + [item[0] for item in compression_options]), ('quantize', 0), ('optimize', True)], title='PNG Options')
                compression = compression_options[compression_index-1][1]
            else:
                compression = options.get('compression', 'Default')
                quantize = options.get('quantize', 0)
                optimize = options.get('optimize', True)

            if quantize == 0: quantize = None

            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, image, format, compression=compression,
                    quantize=quantize, optimize=optimize, prefer_uint8=False)

        else:
            with gui.qapp.waitCursor(f'Saving to {filepath}'):
                imageio.imwrite(filepath, image, format)          
                
                
    def save_image_pil(self, image, filepath):
        
        with gui.qapp.waitCursor():
            
            image = PilImage.fromarray(self.ndarray)
            image.save(str(filepath))                                 
        
        
    def send_array_to_gdesk(self):
        port = gui._qapp.cmdserver.port
        hostname = 'localhost'
        
        form = [('port', port), ('host', hostname), ('new panel', False)]
        results = fedit(form, title='Send Array to Host')
        if results is None: return
        
        port = results[0]        
        hostname = results[1]
        new = results[2]
        
        client.send_array_to_gui(self.basePanel.ndarray, port, hostname, new)        