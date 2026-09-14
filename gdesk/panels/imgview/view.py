import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

from qtpy import QtCore, QtGui
from qtpy.QtWidgets import QAction, QMenu, QColorDialog, QApplication

from .quantiles import get_sigma_range_for_hist

from ...panels import CheckMenu
from ...gcore.utils import ActionArguments
from ...dialogs.formlayout import fedit
from ...dialogs.colormap import ColorMapDialog
from ...utils import imconvert

from ... import config, gui

RESPATH = Path(config['respath'])


def wrap(func, *args, **kwargs):
    def wrapper():
        func(*args, **kwargs)
        
    return wrapper    


class ViewMenu(CheckMenu):
    
    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)    
        
        self.basePanel = basePanel 
        
        # To DO
        # offset, gain, gamma, colormap should be part of the imviewer
        self.offset = 0
        self.white = 256
        self.gamma = 1
        self.colormap = config['image color map']

        self.defaults = dict()
        self.defaults['offset'] = 0
        self.defaults['gain'] = 1
        self.defaults['gamma'] = 1
        
        basePanel.addMenuItem(self, 'Refresh', self.refresh,
            statusTip="Refresh the image", icon = 'update.png')
        basePanel.addMenuItem(self, 'Zoom In' , self.zoomIn,
            statusTip="Zoom in 1 step", icon = 'zoom_in.png')
        basePanel.addMenuItem(self, 'Zoom Out', self.zoomOut,
            statusTip="Zoom out 1 step", icon = 'zoom_out.png')

        zoomMenu = QMenu('Zoom')
        zoomMenu.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom.png')))
        self.addMenu(zoomMenu)
        
        basePanel.addMenuItem(zoomMenu, 'Zoom 100%', self.setZoom100,
            statusTip="Zoom to a actual size (100%)",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_actual.png')))
        basePanel.addMenuItem(zoomMenu, 'Zoom 800%', lambda: self.setZoomValue(8),
            statusTip="Zoom to 800%")
        basePanel.addMenuItem(zoomMenu, 'Zoom 12500%', lambda: self.setZoomValue(125),
            statusTip="Zoom to 12500%")                        
        basePanel.addMenuItem(zoomMenu, 'Zoom Fit'     , self.zoomFit,
            statusTip="Zoom to fit the image in the image viewer, snap on predefined zoom value",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_fit.png')))
        basePanel.addMenuItem(zoomMenu, 'Zoom Full'    , self.zoomFull,
            statusTip="Zoom to fit the image in the image viewer",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_extend.png')))
        basePanel.addMenuItem(zoomMenu, 'Zoom Auto'    , self.zoomAuto,
            statusTip="Toggle between to to selection and full image",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_refresh.png')))
        basePanel.addMenuItem(zoomMenu, 'Zoom exact...'     , self.setZoom,
            statusTip="Zoom to a defined value",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_actual_equal.png')))

        self.addSeparator()

        basePanel.addMenuItem(self, 'Default Offset && Gain', self.defaultOffsetGain,
            statusTip="Apply default offset, gain and gamma",
            icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'unmark_to_download.png')))
            
        self.defaultGainMenu = QMenu('Set Default Gain')
        self.addMenu(self.defaultGainMenu)
        basePanel.addMenuItem(self.defaultGainMenu, 'Set Current as Default', self.setCurrentOffsetGainAsDefault,
            statusTip="Set the current offset, gain and gamma as default")            
        basePanel.addMenuItem(self.defaultGainMenu, 'Increase Default Gain', lambda: self.modifyDefaultGain(1))            
        basePanel.addMenuItem(self.defaultGainMenu, 'Decrease Default Gain', lambda: self.modifyDefaultGain(-1))            
            
        basePanel.addMenuItem(self, 'Offset && Gain...', self.offsetGainDialog,
            statusTip="Set offset and gain",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'weather_cloudy.png')))
        basePanel.addMenuItem(self, 'Black && White...', self.blackWhiteDialog,
            statusTip="Set the black and white point",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_adjustment.png')))
        basePanel.addMenuItem(self, 'Grey && Gain...', self.changeGreyGainDialog,
            statusTip="Set the mid grey level and gain",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast.png')))
        basePanel.addMenuItem(self, 'Gain to Min-Max', self.gainToMinMax,
            statusTip="Auto level to min and max")
        self.gainSigmaMenu = QMenu('Gain to Sigma')
        self.addMenu(self.gainSigmaMenu)
        basePanel.addMenuItem(self.gainSigmaMenu, 'Gain to Sigma 1', self.gainToSigma1)
        basePanel.addMenuItem(self.gainSigmaMenu, 'Gain to Sigma 2', self.gainToSigma2)
        basePanel.addMenuItem(self.gainSigmaMenu, 'Gain to Sigma 3', self.gainToSigma3)

        self.addSeparator()

        basePanel.addMenuItem(self, 'HQ Zoom Out', self.toggle_hq,
            checkcall = lambda: self.imviewer.hqzoomout,
            statusTip = "Use high quality resampling on zoom levels < 100%")
            
        self.bindMenu = CheckMenu("Bind", self)
        self.bindMenu.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'image_link.png')))
        basePanel.addMenuItem(self.bindMenu, 'Bind All Image Viewers', self.bindImageViewers)
        basePanel.addMenuItem(self.bindMenu, 'Unbind All Image Viewers', self.unbindImageViewers)        
        basePanel.addMenuItem(self.bindMenu, 'Absolute Zoom Link', self.toggle_zoombind,
            checkcall = lambda: self.imviewer.zoombind,
            statusTip = "If binded to other image viewer, bind with absolute zoom value")        
        
        basePanel.addMenuItem(self, 'Colormap...'    , self.setColorMap,
            statusTip="Set the color map for monochrome images",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'dopplr.png')))
        basePanel.addMenuItem(self, 'Background Color...'    , self.setBackground,
            statusTip="Set the background color...",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'document_background.png')))
        
        basePanel.addMenuItem(self, 'Mask Appearance...'    , self.setMaskApperance,
            statusTip="Set the mask appearance...",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'mask.png')))

        basePanel.addMenuItem(self, 'Selection Color...'    , self.setRoiColor,
            statusTip="Set the Selection color...",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_swatch.png')))

        self.chooseValFormat = QMenu('Value Format')
        self.chooseValFormat.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'pilcrow.png')))
        self.chooseValFormat.addAction(QAction("Decimal", self, triggered=lambda: self.statuspanel.set_val_format('dec')))
        self.chooseValFormat.addAction(QAction("Hex", self, triggered=lambda: self.statuspanel.set_val_format('hex')))
        self.chooseValFormat.addAction(QAction("Binary", self, triggered=lambda: self.statuspanel.set_val_format('bin')))
        self.chooseValFormat.addAction(QAction("Pixel Labels", self, triggered=self.togglePixelLabels))
        self.addMenu(self.chooseValFormat)            
            

    @property
    def imviewer(self):
        return self.basePanel.imviewer
        
        
    @property
    def ndarray(self):
        return self.basePanel.ndarray        
        
    
    @property    
    def imgprof(self):
        return self.basePanel.imgprof
        
        
    def refresh(self):
        self.basePanel.refresh()   
               
        
    def refresh_offset_gain(self, array=None, zoomFitHist=False, log=True, skip_init=False):
        self.imviewer.imgdata.show_array(array, self.offset, self.white, self.colormap, self.gamma, log, skip_init)
        self.statuspanel.setOffsetGainInfo(self.offset, self.gain, self.white, self.gamma)
        self.basePanel.gainChanged.emit(self.basePanel.panid, zoomFitHist)
        self.refresh()        


    def show_array(self, array, zoomFitHist=False, log=True, skip_init=False):
        self.refresh_offset_gain(array, log=log, skip_init=skip_init)                   
        self.basePanel.contentChanged.emit(self.basePanel.panid, zoomFitHist)
        
    
    @property
    def statuspanel(self):
        return self.basePanel.statuspanel
        
        
    ###################
    
    def zoomIn(self):
        self.imviewer.zoomIn()
        

    def zoomOut(self):
        self.imviewer.zoomOut()  


    def setZoom100(self):
        self.setZoomValue(1)          
        
        
    def setZoomValue(self, value):
        self.imviewer.setZoom(value)        
        

    def zoomFit(self):
        self.imviewer.zoomFit()
        

    def zoomFull(self):
        self.imviewer.zoomFull()
        

    def zoomAuto(self):
        self.imviewer.zoomAuto()        
        
        
    def setZoom(self):
        with ActionArguments(self) as args:
            args['zoom'] = self.imviewer.zoomValue * 100

        if args.isNotSet():
            results = fedit([('Zoom value %', args['zoom'])], title='Set Zoom')
            if results is None: return
            args['zoom'] = results[0]

        self.setZoomValue(args['zoom'] / 100)
        
    #--------------------------------
    
    def defaultOffsetGain(self):
        offset = self.defaults['offset']
        gain = self.defaults['gain']
        gamma = self.defaults['gamma']
        self.changeOffsetGain(offset, gain, gamma)
        
        
    def setCurrentOffsetGainAsDefault(self):
        self.defaults['offset'] = self.offset
        self.defaults['gain'] = self.gain
        self.defaults['gamma'] = self.gamma        
        
        
    def modifyDefaultGain(self, step=1):        
        if step > 0:
            new_default = 2 ** np.floor(np.log2(self.gain) + step)
        else:
            new_default = 2 ** np.ceil(np.log2(self.gain) + step)
            
        self.defaults['gain'] = new_default
        self.defaultOffsetGain()          


    def get_gain(self):
        natrange = self.imviewer.imgdata.get_natural_range()
        gain = natrange / (self.white - self.offset)
        return gain
        
        
    def set_gain(self, gain):
        natrange = self.imviewer.imgdata.get_natural_range()
        self.white = self.offset + natrange / gain
        
        
    gain = property(get_gain, set_gain)

    def offsetGainDialog(self):

        with ActionArguments(self) as args:
            args['offset'] = self.offset
            args['gain'] = self.gain
            args['gamma'] = self.gamma
            args['cmap'] = self.colormap

        if args.isNotSet():
            colormaps = imconvert.colormaps
            cmapind = colormaps.index(self.colormap) + 1

            form = [('Offset', self.offset * 1.0),
                    ('Gain', self.gain * 1.0),
                    ('Gamma', self.gamma * 1.0),
                    ('Color Map', [cmapind] + colormaps)]

            results = fedit(form, title = 'Offset & Gain')
            if results is None: return
            offset, gain, gamma, cmapind = results
            self.colormap = colormaps[cmapind-1]

        else:
            offset, gain = args['offset'], args['gain']
            gamma, self.colormap = args['gamma'], args['cmap']

        self.changeOffsetGain(offset, gain, gamma)         


    def changeOffsetGain(self, offset, gain, gamma, reset_levels=True):
        if isinstance(offset, str):
            if offset == 'default':
                offset = self.defaults['offset']
            else:
                offset = eval(offset)
        if isinstance(gain, str):
            if gain == 'default':
                gain = self.defaults['gain']
            else:
                gain = eval(gain)
        if isinstance(gamma, str):
            if gamma == 'default':
                gamma = self.defaults['gamma']
            else:
                gamma = eval(gamma)

        if not offset is None: self.offset = offset
        if not gain is None: self.gain = gain
        if not gamma is None: self.gamma = gamma
        self.refresh_offset_gain(zoomFitHist=reset_levels)
        

    def blackWhiteDialog(self):

        with ActionArguments(self) as args:
            args['black'] = self.offset
            args['white'] = self.white
            args['cmap'] = self.colormap

        if args.isNotSet():
            colormaps = imconvert.colormaps
            cmapind = colormaps.index(self.colormap) + 1

            black = self.offset
            gain1_range = self.imviewer.imgdata.get_natural_range()

            form = [('Black', black),
                    ('White', self.white),
                    ('Color Map', [cmapind] + colormaps)]

            results = fedit(form, title='Black & White')
            if results is None: return
            black, white, cmapind = results
            self.colormap = colormaps[cmapind-1]

        else:
            black, white = args['black'], args['white']
            self.colormap  = args['cmap']

        self.changeBlackWhite(black, white)
        

    def changeBlackWhite(self, black, white):
        if isinstance(black, str):
            black = eval(black)
        if isinstance(white, str):
            white = eval(white)

        if black == white:
            print(f'Warning: black and white are set the same ({black}). Setting to mid grey!')
            self.changeMidGrey(black)
            return

        gain1_range = self.imviewer.imgdata.get_natural_range()

        if not (black is None or white is None):
            self.offset = black
            self.gain = gain1_range / (white - black)
        elif white is None:
            white = self.white
            self.offset = black
            self.gain = gain1_range / (white - self.offset)
        elif black is None:
            self.gain = gain1_range / (white - self.offset)

        self.refresh_offset_gain()
        

    def changeGreyGainDialog(self):

        gain1_range = self.imviewer.imgdata.get_natural_range()
        grey = self.offset + gain1_range / self.gain / 2

        with ActionArguments(self) as args:
            args['grey'] = grey
            args['gain'] = self.gain
            args['cmap'] = self.colormap

        if args.isNotSet():
            colormaps = imconvert.colormaps
            cmapind = colormaps.index(self.colormap) + 1

            form = [('Grey', grey),
                    ('Gain', self.gain * 1.0),
                    ('Color Map', [cmapind] + colormaps)]

            results = fedit(form, title='Grey & Gain')
            if results is None: return
            grey, gain, cmapind = results
            self.colormap = colormaps[cmapind-1]

        else:
            grey = args['grey']
            gain = args['gain']
            self.colormap = args['cmap']

        self.changeMidGrey(grey, gain)
        

    def changeMidGrey(self, midgrey, gain=None):
        if not gain is None: self.gain = gain
        gain1_range = self.imviewer.imgdata.get_natural_range()
        self.offset = midgrey - gain1_range / self.gain / 2
        self.refresh_offset_gain()
        

    def gainToMinMax(self):
        black = self.ndarray.min()
        white = self.ndarray.max()
        self.changeBlackWhite(black, white)
        

    def gainToSigma1(self):
        self.gainToSigma(1)
            

    def gainToSigma2(self):
        self.gainToSigma(2)
            

    def gainToSigma3(self):
        self.gainToSigma(3)
            

    def gainToSigma(self, sigma=3, roi=None):
        chanstats = self.imviewer.imgdata.chanstats        

        blacks = dict()
        whites = dict()
        
        skip_dim = not all(stats.dim for stats in self.imviewer.imgdata.chanstats.values() if (stats.is_valid() and stats.active))
        
        for clr, stats in  self.imviewer.imgdata.chanstats.items():            
            if not (stats.is_valid() and stats.active): continue
            if skip_dim and stats.dim: continue
            
            hist = stats.histogram(1)
            starts = stats.starts(1)
            blacks[clr], whites[clr] = get_sigma_range_for_hist(starts, hist, sigma)

        black = min(blacks.values())
        white = max(whites.values())

        if self.ndarray.dtype in ['uint8', 'uint16']:
            if black == white:
                return
            else:
                white += 1

        self.changeBlackWhite(black, white)   


    #------------------       
        
    # def zoomToRoi(self):
        # self.imviewer.zoomToRoi()
        
        
    # def zoomToRegion(self, x, y, width, height):        
        # self.imviewer.zoomToRegion(x, y, width, height)
        
        
    def toggle_hq(self):
        self.imviewer.hqzoomout = not self.imviewer.hqzoomout
        self.show_array(None)
        
        
    def bindImageViewers(self):
        for src_panid, src_panel in gui.qapp.panels['image'].items():
            for tgt_panid, tgt_panel in gui.qapp.panels['image'].items():            
                if src_panid == tgt_panid: continue
                src_panel.addBindingTo('image', tgt_panid)
                
                
    def unbindImageViewers(self):
        for src_panid, src_panel in gui.qapp.panels['image'].items():
            for tgt_panid, tgt_panel in gui.qapp.panels['image'].items():            
                if src_panid == tgt_panid: continue
                src_panel.removeBindingTo('image', tgt_panid)          
                
                
    def toggle_zoombind(self):
        self.imviewer.zoombind = not self.imviewer.zoombind                
                        

    def setColorMap(self):
        with ActionArguments(self) as args:
            args['cmap'] = 'grey'

        if args.isNotSet():
            colormapdialog = ColorMapDialog()
            colormapdialog.exec_()
            if not colormapdialog.cm_name is None:
                self.colormap = colormapdialog.cm_name
        else:
            self.colormap = args['cmap']

        self.refresh_offset_gain()                     
                

    def setBackground(self):
        old_color = self.imviewer.palette().window().color()
        rgb = old_color.getRgb()[:3]
        with ActionArguments(self) as args:
            args['r'] = rgb[0]
            args['g'] = rgb[1]
            args['b'] = rgb[2]

        if args.isNotSet():
            color = QColorDialog.getColor(old_color)
            try:
                rgb = color.getRgb()[:3]
            except:
                rgb = (0,0,0)
        else:
            rgb = (args['r'], args['g'], args['b'])

        color_scheme = QApplication.instance().color_scheme
        if color_scheme == "Dark":
            config["image background dark"] = rgb
            self.imviewer.setBackgroundColor(*config["image background dark"])
        else:
            config["image background"] = rgb
            self.imviewer.setBackgroundColor(*config["image background"])


    def setMaskApperance(self):
        old_color = QtGui.QColor(*config.get('mask color', (255,0,0)))
        rgb = old_color.getRgb()[:3]
        with ActionArguments(self) as args:
            args['r'] = rgb[0]
            args['g'] = rgb[1]
            args['b'] = rgb[2]

        if args.isNotSet():
            color = QColorDialog.getColor(old_color)
            try:
                rgb = color.getRgb()[:3]
            except:
                rgb = (0,0,0)
        else:
            rgb = (args['r'], args['g'], args['b'])

        if 'mask' in self.imviewer.imgdata.layers:
            self.imviewer.imgdata.change_layer_appearance('mask', color=rgb)

        config['mask color'] = list(rgb)
        self.refresh()


    def setRoiColor(self):
        old_color = QtGui.QColor(*config['roi color'])
        rgb = old_color.getRgb()[:3]
        with ActionArguments(self) as args:
            args['r'] = rgb[0]
            args['g'] = rgb[1]
            args['b'] = rgb[2]
            
        if args.isNotSet():
            color = QColorDialog.getColor(old_color)
            try:
                rgb = color.getRgb()[:3]
            except:
                rgb = (0,0,0)
                
        else:
            rgb = (args['r'], args['g'], args['b'])                
            
        config['roi color'] = list(rgb)
        self.imviewer.roi.initUI()        


    def roiSelected(self, roi_name):
        # roi_names = roi_name.split(',')
        # self.imviewer.imgdata.highLightRois(roi_names)
        # self.refresh()
        self.imgprof.selectMask(roi_name)
        

    def togglePixelLabels(self):
        v = config['image'].get('pixel_labels', False)
        config['image']['pixel_labels'] = not v        
   
