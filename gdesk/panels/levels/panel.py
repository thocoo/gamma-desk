import pathlib
import numpy as np 

from qtpy import QtCore, QtGui, QtWidgets

from ... import config, gui

from ...graphics.view import SceneView
from ...graphics.items import createCurve, Indicator
from ...graphics.rulers import TickedRuler, Grid
from ...graphics.point import Point
from ..base import BasePanel, CheckMenu

from ..imgview import fasthist

respath = pathlib.Path(config['respath'])

colors = {
    'K': QtGui.QColor(0, 0, 0),
    'RK': QtGui.QColor(255, 0, 0),
    'R': QtGui.QColor(255, 0, 0),
    'G': QtGui.QColor(0, 255, 0),
    'B': QtGui.QColor(0, 0, 255),
    'RR': QtGui.QColor(192, 0, 0),
    'RG': QtGui.QColor(64, 127, 0),
    'RB': QtGui.QColor(64, 0, 127)}    

class LevelPlot(QtWidgets.QWidget):
    
    blackPointChanged = QtCore.Signal(object)
    whitePointChanged = QtCore.Signal(object)
    
    def __init__(self, parent):
        super().__init__(parent=parent)
        
        self.scene = QtWidgets.QGraphicsScene()
        self.view = SceneView(self)  
        self.view.freeze_y0 = True
        
        self.view.scale = [100, -100]
        self.view.setScene(self.scene)
        
        #self.view.fixScaleY = True
        
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.addWidget(self.view)
        self.setLayout(self.vbox)
        
        self.create_x_ruler()
        self.create_y_ruler()
        # self.create_grid()       
        
        self.indicators = []
        
        self.create_indicator(0, QtGui.QColor(0,0,127), 'B:%0.5g', self.IndicatorBMoved)                        
        self.create_indicator(256, QtGui.QColor(255,127,127), 'W:%0.5g', self.IndicatorWMoved)        
        
        self.curves = dict()                      
        self.plot_curve('K', [0, 256], [0, 0])
        #self.plot_curve('G', [-2, -1, 0 , 1, 2], [0, 0.5, 1.0, 0.5 ,0])
        #self.plot_curve('B', [-2, -1, 0 , 1, 2], [1, 1.0, 1.0, 0.25 ,0])
        
        for indicator in self.indicators:
            indicator.attach_curves(self.curves)
        
        self.view.translated.connect(self.update_rulers)
        self.view.scaled.connect(self.update_rulers)
        self.view.scale_ended.connect(self.update_rulers)   
        self.view.zoom_full.connect(self.zoomFull)   
        
        self.xmin = 0
        self.xmax = 1e6
        self.ymin = 0
        self.ymax = 256

    def create_indicator(self, xpos, color, text = None, slot=None):
        indicator = Indicator(color, text, parent=self.x_ruler)
        indicator.setPos(xpos, 0)
        indicator.setZValue(2.0)
        indicator.mouse_released.connect(slot)
        self.indicators.append(indicator)
        #self.scene.addItem(indicator)
        
    def create_x_ruler(self):
        x0, y0, x1, y1 = self.view.viewRectCoord()
        self.x_ruler = TickedRuler(0, x0, x1, abs(self.view.scale[0]), noDecimals=False, parent=None)       
        self.v_grid = Grid(self.x_ruler,  parent=None)
        self.x_ruler.setPos(0, y0 - self.view.pixelSize()[1] * 22)     
        self.v_grid.setPos(0, y0 - self.view.pixelSize()[1] * 22)     
        self.x_ruler.setZValue(1.0)
        self.v_grid.setZValue(-1)
        self.scene.addItem(self.x_ruler)              
        self.scene.addItem(self.v_grid)              
        
    def create_y_ruler(self):
        x0, y0, x1, y1 = self.view.viewRectCoord()
        self.y_ruler = TickedRuler(-90, y0, y1, abs(self.view.scale[1]), noDecimals=False)  
        self.h_grid = Grid(self.y_ruler)        
        self.y_ruler.setPos(x0 + self.view.pixelSize()[0] * 22, 0)     
        self.h_grid.setPos(x0 + self.view.pixelSize()[0] * 22, 0)     
        self.y_ruler.setZValue(0.9)
        self.h_grid.setZValue(-1)
        self.scene.addItem(self.y_ruler)          
        self.scene.addItem(self.h_grid)          
        
    def attach_indicators(self):
        for indicator in self.indicators:
            indicator.setParentItem(self.x_ruler)
            
    def hide_stuff(self):
        self.x_ruler.hide()
        self.y_ruler.hide()
                
    def update_x_ruler(self):        
        x0, y0, x1, y1 = self.view.viewRectCoord()
        self.x_ruler.setPos(0, y0 - self.view.pixelSize()[1] * 22)
        self.x_ruler.update_labels(x0, x1, abs(self.view.scale[0]))
        self.v_grid.setPos(0, y0 - self.view.pixelSize()[1] * 22)
        self.v_grid.update_labels()
        
        self.x_ruler.show()
        #self.xmin = x0
        #self.xmax = x1     
        
    def update_y_ruler(self): 
        x0, y0, x1, y1 = self.view.viewRectCoord()
        self.y_ruler.setPos(x0 + self.view.pixelSize()[0] * 22, 0)
        self.y_ruler.update_labels(y0, y1, abs(self.view.scale[1]))
        self.h_grid.setPos(x0 + self.view.pixelSize()[0] * 22, 0)
        self.h_grid.update_labels()        
        self.y_ruler.show()  

        for indicator in self.indicators:
            indicator.updates_ylabels()         
            
        self.ymin = y0 - self.view.pixelSize()[1] * 22
        self.ymax = y1

    def update_rulers(self, x, y):  
        self.update_x_ruler()
        self.update_y_ruler()   

    def remove_all_but(self, curve_ids):
        for curveid in list(self.curves.keys()):
            if curveid in curve_ids:
                continue
            oldcurve = self.curves[curveid]
            self.scene.removeItem(oldcurve)
            self.curves.pop(curveid)
        
    def plot_curve(self, curveid=None, x=[], y=[], color = None):
        oldcolor = None
        
        if curveid in self.curves.keys():
            oldcurve = self.curves[curveid]
            oldcolor = oldcurve.pen().color()
            self.scene.removeItem(oldcurve)
            
        elif curveid is None:            
            curveid = len(self.curves)            
        
        if color is None:
            if oldcolor is None:
                color = colors[curveid]
            else:
                color = oldcolor
            
        curve = createCurve(x, y, color = color)
        curve.setZValue(0)            
        
        self.curves[curveid] = curve                     
        self.scene.addItem(curve)
        
        return curveid
        
    def zoomFull(self, enforce_ymin=None):
        self.xmin = self.xmax = None
        self.ymin = self.ymax = None
        
        for curve in self.curves.values():
            xmin_cand = min(curve.xvector)
            xmax_cand = max(curve.xvector)
            ymin_cand = min(curve.yvector)
            ymax_cand = max(curve.yvector)            
            if (self.xmin is None) or (xmin_cand < self.xmin):
                self.xmin = xmin_cand            
            if (self.xmax is None) or (xmax_cand > self.xmax):
                self.xmax = xmax_cand
            if (self.ymin is None) or (ymin_cand < self.ymin):
                self.ymin = ymin_cand            
            if (self.ymax is None) or (ymax_cand > self.ymax):
                self.ymax = ymax_cand
                        
        self.ymin = enforce_ymin if not enforce_ymin is None else self.ymin
        
        if self.xmin == self.xmax:
            self.xmin -= 0.5
            self.xmin += 0.5
            
        if self.ymin == self.ymax:
            self.ymin -= 0.5
            self.ymax += 0.5
                    
        self.view.setXLimits(self.xmin, self.xmax, 22, 0)
        self.view.setYLimits(self.ymin, self.ymax, 22, 0)
        #self.resetIndicators(self.xmin, self.xmax)
        self.update_rulers(True, True)
        
    def zoomFitYRange(self, ymin=None):
        self.ymin = self.ymax = None

        for curve in self.curves.values():
            ymin_cand = min(curve.yvector)
            ymax_cand = max(curve.yvector)            
            if (self.ymin is None) or (ymin_cand < self.ymin):
                self.ymin = ymin_cand
            if (self.ymax is None) or (ymax_cand > self.ymax):
                self.ymax = ymax_cand  
                
        self.ymin = ymin if not ymin is None else self.ymin

        if self.ymin == self.ymax:
            self.ymin -= 0.5
            self.ymax += 0.5  

        self.view.setYLimits(self.ymin, self.ymax, 22, 0)
        self.update_rulers(True, True)
        
    def zoomBetweenIndicators(self):
        x0 = self.indicators[0].pos().x()
        x1 = self.indicators[1].pos().x()
        self.view.setXLimits(x0, x1, 22, 0)
        self.update_rulers(True, True)                           
        
    def resetIndicators(self, xmin=0, xmax=1):
        for indicator in self.indicators:
            x = indicator.pos().x()
            x = min(max(x, xmin), xmax)
            indicator.setPos(x, 0)    
                        
    def IndicatorBMoved(self, val):
        self.blackPointChanged.emit(val)
        
    def IndicatorWMoved(self, val):
        self.whitePointChanged.emit(val)     

    def resizeEvent(self, ev):
        self.view.setYLimits(self.ymin, self.ymax, 22, 0)
        self.update_rulers(True, True)         
        
       
class Levels(QtWidgets.QWidget):    
        
    def __init__(self, parent=None):         
        self.panel = parent
        super().__init__(parent=parent)                
        self.initUI()
        
    def initUI(self):                            
        self.setMinimumHeight(80)
        self.setMinimumWidth(200)    

        self.hbox = QtWidgets.QHBoxLayout()         
        self.hbox.addStretch()                
                
        self.levelplot = LevelPlot(self)                                         
                         
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.setSpacing(0)
        self.setLayout(self.vbox)        
        self.vbox.addLayout(self.hbox)                
        self.vbox.addWidget(self.levelplot)                                                 

    #@staticmethod
    def image_panel(self, panel_id=None):
        if (panel_id is None) or (panel_id==False):        
            imagePanel = self.panel.bindedPanel('image')
            if imagePanel is None:
                imagePanel = gui.qapp.panels.selected('image')            
        else:            
            imagePanel = gui.qapp.panels['image'][panel_id] 
        return imagePanel                              
       
    @staticmethod       
    def xy_as_steps(xvector, yvector, stepwidth):
        yvector = yvector.reshape((yvector.shape[0], 1)).dot(np.ones((1, 2))).reshape(yvector.shape[0]*2)            
        xvector = xvector.reshape((xvector.shape[0], 1)).dot(np.ones((1, 2)))
        xvector[:,1] += stepwidth
        xvector = xvector.flatten()
        return xvector, yvector  
        
    def updateActiveHist(self):
        if self.panel.cached:
            self.updatedCachedHistogram(None)            
        else:
            self.updateHist(None)
        
        self.levelplot.zoomFitYRange(ymin=0)
            
    def updateHistOfPanel(self, panelId=None):
        if self.panel.cached:
            self.updatedCachedHistogram(panelId)            
        else:
            self.updateHist(panelId)        
            
        self.levelplot.zoomFitYRange(ymin=0)

    def updatedCachedHistogram(self, panid):      
        image_panel = self.image_panel(panid)
        chanstats = image_panel.imviewer.imgdata.chanstats 
        
        if self.panel.histSizePolicy == 'bins':
            bins = int(self.panel.histSize)               
        else:
            bins = None
            stepsize = int(self.panel.histSize)
        
        if self.panel.roi and image_panel.imviewer.roi.isVisible():
            clr_filter = set(('RK','RR', 'RG', 'RB'))
        else:
            clr_filter = set(('K', 'R', 'G', 'B'))
        
        clr_to_draw = clr_filter.intersection(set(chanstats.keys()))
        self.levelplot.remove_all_but(clr_to_draw)
        
        for clr in clr_to_draw: 
            chanstat = chanstats[clr]
            if chanstat.arr2d is None: continue
            step = stepsize if bins is None else chanstat.step_for_bins(bins)            
            hist = chanstat.histogram(step)
            if self.panel.sqrt:
                hist = hist ** 0.5              
            starts = chanstat.starts(step)            
            starts, hist = self.xy_as_steps(starts, hist, chanstat.stepsize(step))
            self.levelplot.plot_curve(clr, starts, hist) 
        
    def updateHist(self, panelId=None):
        qapp = gui.qapp
        with qapp.waitCursor():        
            use_numba = config['levels']['numba']
            relative = config['levels']['relative']
            hist2d = fasthist.hist2d                
            
            imagePanel = self.image_panel(panid)                   
                
            do_roi = self.panel.roi and imagePanel.imviewer.roi.isVisible()            

            if do_roi: 
                slices = imagePanel.imviewer.imgdata.selroi.getslices()
                arr = imagePanel.ndarray[slices]
            else:
                arr = imagePanel.ndarray    
                
            if len(arr.shape) == 2:        
                if self.panel.histSizePolicy == 'bins':
                    stepcount = int(self.panel.histSize)
                    hist, starts, stepsize = hist2d(arr, bins=stepcount-1, plot=False, use_numba=use_numba)
                    if self.panel.sqrt:
                        hist = hist ** 0.5
                    self.stepsize.setText(str(stepsize))
                    
                elif self.panel.histSizePolicy == 'step':
                    stepsize = int(self.panel.histSize)
                    hist, starts, stepsize = hist2d(arr, step=stepsize, pow2snap=True, plot=False, use_numba=use_numba)
                    if self.panel.sqrt:
                        hist = hist ** 0.5                
                    self.stepcount.setText(str(len(hist)))        
                
                if relative:
                    hist = hist /  (arr.shape[0] * arr.shape[1] * stepsize)
                    
                starts, hist = self.xy_as_steps(starts, hist, stepsize)
                
                if do_roi:
                    self.levelplot.remove_all_but(['RK'])
                    self.levelplot.plot_curve('RK', starts, hist)            
                else:
                    self.levelplot.remove_all_but(['K'])
                    self.levelplot.plot_curve('K', starts, hist)                            
                
            elif len(arr.shape) == 3 and do_roi:
            
                self.levelplot.remove_all_but(['RR','RG','RB'])
                for clr_ch, clr_str in [(0,'RR'),(1,'RG'),(2,'RB')]:        
                    if self.panel.histSizePolicy == 'bins':
                        stepcount = int(self.panel.histSize)
                        hist, starts, stepsize = hist2d(arr[:,:,clr_ch], bins=stepcount-1, plot=False, use_numba=use_numba)     
                        if self.panel.sqrt:
                            hist = hist ** 0.5
                        self.stepsize.setText(str(stepsize))                    
                        
                    elif self.panel.histSizePolicy == 'step':
                        stepsize = int(self.panel.histSize)
                        hist, starts, stepsize = hist2d(arr[:,:,clr_ch], step=stepsize, pow2snap=True, plot=False, use_numba=use_numba)            
                        if self.panel.sqrt:
                            hist = hist ** 0.5                
                        self.stepcount.setText(str(len(hist)))
                        
                    if relative:
                        hist = hist /  (arr.shape[0] * arr.shape[1] * stepsize)
                        
                    starts, hist = self.xy_as_steps(starts, hist, stepsize)                 
                    self.levelplot.plot_curve(clr_str, starts, hist) 
                    
            elif len(arr.shape) == 3 and not do_roi:     
            
                self.levelplot.remove_all_but(['R','G','B'])
                for clr_ch, clr_str in [(0,'R'),(1,'G'),(2,'B')]:        
                    if self.step_priority == 'stepcount':
                        stepcount = eval(self.stepcount.text())
                        hist, starts, stepsize = hist2d(arr[:,:,clr_ch], bins=stepcount-1, plot=False, use_numba=use_numba)     
                        if self.panel.sqrt:
                            hist = hist ** 0.5
                        self.stepsize.setText(str(stepsize))                    
                        
                    elif self.step_priority == 'stepsize':
                        stepsize = eval(self.stepsize.text())
                        hist, starts, stepsize = hist2d(arr[:,:,clr_ch], step=stepsize, pow2snap=True, plot=False, use_numba=use_numba)            
                        if self.panel.sqrt:
                            hist = hist ** 0.5                
                        self.stepcount.setText(str(len(hist)))
                        
                    if relative:
                        hist = hist /  (arr.shape[0] * arr.shape[1] * stepsize)                    
                        
                    starts, hist = self.xy_as_steps(starts, hist, stepsize)                 
                    self.levelplot.plot_curve(clr_str, starts, hist)  
        

    def updateIndicators(self, image_panel_id):
        qapp = gui.qapp
        
        if (image_panel_id is None) or (image_panel_id==False):            
            imagePanel =  qapp.panels.selected('image')
            
        else:            
            imagePanel = qapp.panels['image'][image_panel_id]
        
        ind = self.levelplot.indicators[0]
        ind.setPos(imagePanel.offset, 0)
        ind.label.updateText(ind.text % imagePanel.offset)
        ind.updates_ylabels()
        
        ind = self.levelplot.indicators[1]
        ind.setPos(imagePanel.white, 0)
        ind.label.updateText(ind.text % imagePanel.white)
        ind.updates_ylabels()        
            
    def indicZoom(self):
        self.levelplot.zoomBetweenIndicators()
        
    def fullZoom(self):
        self.levelplot.zoomFull(enforce_ymin=0)        

    def zoomFitYRange(self):
        self.levelplot.zoomFitYRange(ymin=0)           
        
    # def focusInEvent(self, event):
        # self.parent().select()     

class LevelsToolBar(QtWidgets.QToolBar):
    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()

    @property
    def panel(self):
        return self.parent()       
        
    @property
    def levels(self):
        return self.parent().levels
        
    def initUi(self):
        self.addAction(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'update.png')), 'Refresh', self.levels.updateActiveHist)
        
        self.histSizePolicyBox = QtWidgets.QComboBox()
        self.histSizePolicyBox.addItem('bins')
        self.histSizePolicyBox.addItem('step')
        self.histSizePolicyBox.currentTextChanged.connect(self.histSizePolicyChanged)
        self.addWidget(self.histSizePolicyBox)        
        
        self.stepcount = QtWidgets.QLineEdit('64', self)
        self.stepcount.setMaximumWidth(100)
        self.stepcount.textChanged.connect(self.histSizeChanged)
        self.addWidget(self.stepcount)
        
        self.addAction(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'unmark_to_download.png')), 'Apply default offset, gain and gamma', self.panel.gain1)  
        
        self.gainSigmaMenu = QtWidgets.QMenu('Contrast')
        actGainSigma1 = QtWidgets.QAction('Gain to Sigma 1', self, triggered=lambda: self.panel.autoContrast(1))
        actGainSigma1.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'contrast_high.png')))        
        self.gainSigmaMenu.addAction(actGainSigma1)    
        actGainSigma2 = QtWidgets.QAction('Gain to Sigma 2', self, triggered=lambda: self.panel.autoContrast(2))
        actGainSigma2.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'contrast.png')))        
        self.gainSigmaMenu.addAction(actGainSigma2)    
        actGainSigma3 = QtWidgets.QAction('Gain to Sigma 3', self, triggered=lambda: self.panel.autoContrast(3))
        actGainSigma3.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'contrast_low.png')))        
        self.gainSigmaMenu.addAction(actGainSigma3)                         
        self.autoBtn = QtWidgets.QToolButton(self)
        self.autoBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'contrast.png')))
        self.autoBtn.setMenu(self.gainSigmaMenu)
        self.autoBtn.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self.autoBtn.clicked.connect(lambda: self.panel.autoContrast())        
        self.addWidget(self.autoBtn)
        
        self.useRoiBtn = QtWidgets.QToolButton(self)
        self.useRoiBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'region_of_interest.png')))
        self.useRoiBtn.setCheckable(True)
        self.useRoiBtn.clicked.connect(self.toggleRoi)
        self.addWidget(self.useRoiBtn)     
        
        self.sqrtBtn = QtWidgets.QToolButton(self)
        self.sqrtBtn.setIcon(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'square_root.png')))
        self.sqrtBtn.setCheckable(True)
        self.sqrtBtn.clicked.connect(self.toggleSqrt)
        self.addWidget(self.sqrtBtn)         
        
        self.addAction(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_fit.png')), 'Zoom to full histogram', self.levels.fullZoom)        
        self.addAction(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_actual_equal.png')), 'Zoom Fit Y range', self.levels.zoomFitYRange)
        self.addAction(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'zoom_cursors.png')), 'Zoom to black white indicators', self.levels.indicZoom)        
        self.addAction(QtGui.QIcon(str(respath / 'icons' / 'px16' / 'dopplr.png')), 'Choose colormap', self.colorMap)        
        
        fontHeight = self.fontMetrics().height()
        self.setIconSize(QtCore.QSize(fontHeight * 3 / 2, fontHeight * 3 / 2))
        
    def histSizePolicyChanged(self, text):
        self.stepcount.setText(str(self.panel.histSizes[text]))
        
    def histSizeChanged(self, text):
        histSizePolicy = self.histSizePolicyBox.currentText()
        self.panel.histSizePolicy = histSizePolicy
        self.panel.histSizes[histSizePolicy] = text
        
    def toggleRoi(self):
        sender = self.sender()
        self.panel.roi = sender.isChecked()
        self.levels.updateActiveHist()
        
    def toggleSqrt(self):
        sender = self.sender()
        self.panel.sqrt = sender.isChecked()
        self.levels.updateActiveHist()
        
    def updateButtonStates(self):
        self.histSizePolicyBox.setCurrentText(self.panel.histSizePolicy)
        self.useRoiBtn.setChecked(self.panel.roi)
        self.sqrtBtn.setChecked(self.panel.sqrt)
        
    def colorMap(self):
        panids = self.panel.panIdsOfBounded('image')
        for panid in panids:
            gui.menu_trigger('image', panid, ['View','Colormap...'])
        
        
class LevelsPanel(BasePanel):

    panelCategory = 'levels'
    panelShortName = 'basic'
    userVisible = True
    
    offsetGainChanged = QtCore.Signal(object, object, object)    
    blackWhiteChanged = QtCore.Signal(object, object)    
    
    classIconFile = str(respath / 'icons' / 'px16' / 'color_adjustment.png')

    def __init__(self, parent, panid):    
        super().__init__(parent, panid, 'levels')  

        self.histSizePolicy = config['levels'].get('hist_size_policy', 'bins')
        bins = config['levels'].get('bins', 64)
        step = config['levels'].get('step', 4)
        self.histSizes = {'bins': bins, 'step': step}
        
        self.cached = True
        self.sqrt = False
        self.roi = False
        self.sigma = 1
        
        self.levels = Levels(self)
        self.setCentralWidget(self.levels)
        
        self.toolbar = LevelsToolBar(self)
        self.addToolBar(self.toolbar)        
        
        self.fileMenu = self.menuBar().addMenu("&File")
        self.modeMenu = CheckMenu("&Mode", self.menuBar())
        self.menuBar().addMenu(self.modeMenu)        
        
        self.addMenuItem(self.fileMenu, 'Close', self.close_panel,
            statusTip="Close this levels panel",
            icon = QtGui.QIcon(str(respath / 'icons' / 'px16' / 'cross.png')))
        
        self.addMenuItem(self.modeMenu, 'Cached', self.toggle_cached, checkcall=lambda: self.cached)
        self.addMenuItem(self.modeMenu, 'Roi', self.toggle_roi, checkcall=lambda: self.roi)
        self.addMenuItem(self.modeMenu, 'Sqrt', self.toggle_sqrt, checkcall=lambda: self.sqrt)
        
        self.addBaseMenu(['image'])
        
        self.levels.levelplot.blackPointChanged.connect(self.updateBlackPoint)
        self.levels.levelplot.whitePointChanged.connect(self.updateWhitePoint)
        
        self.levels.show()
        self.toolbar.updateButtonStates()
        
        self.statusBar().hide()
        
    @property
    def histSize(self):
        return self.histSizes[self.histSizePolicy]
        
    def addBindingTo(self, category, panid):
        targetPanel = super().addBindingTo(category, panid)
        if targetPanel is None: return None
        self.offsetGainChanged.connect(targetPanel.changeOffsetGain)
        self.blackWhiteChanged.connect(targetPanel.changeBlackWhite)
        return targetPanel
        
    def removeBindingTo(self, category, panid):
        targetPanel = super().removeBindingTo(category, panid)
        if targetPanel is None: return None
        self.offsetGainChanged.disconnect(targetPanel.changeOffsetGain)        
        self.blackWhiteChanged.disconnect(targetPanel.changeBlackWhite)        
        return targetPanel         
        
    def toggle_cached(self):
        self.cached = not self.cached
        self.toolbar.updateButtonStates()
        self.levels.updateActiveHist()
        
    def toggle_roi(self):
        self.roi = not self.roi
        self.toolbar.updateButtonStates()
        self.levels.updateActiveHist()        

    def toggle_sqrt(self):
        self.sqrt = not self.sqrt
        self.toolbar.updateButtonStates()
        self.levels.updateActiveHist()          
        
    def autoContrast(self, sigma=None):
        if not sigma is None:
            self.sigma = sigma
            
        panids = self.panIdsOfBounded('image')
        for panid in panids:
            #gui.menu_trigger('image', panid, ['View', 'Gain to Sigma', f'Gain to Sigma {self.sigma}'])
            gui.qapp.panels['image'][panid].gainToSigma(self.sigma, self.roi)
            
    def gain1(self):    
        self.offsetGainChanged.emit('default', 'default', 'default')
        self.levels.indicZoom()
        
    def updateBlackPoint(self, value):
        self.blackWhiteChanged.emit(value, None)
        
    def updateWhitePoint(self, value):
        self.blackWhiteChanged.emit(None, value)        
        
    def imageContentChanged(self, image_panel_id, zoomFit=False):
        self.levels.updateHistOfPanel(image_panel_id)
        if zoomFit:
            self.levels.fullZoom()

    def imageGainChanged(self, image_panel_id):
        self.levels.updateIndicators(image_panel_id)        
        
    def roiChanged(self, image_panel_id):
        if self.roi:
            self.levels.updateHistOfPanel(image_panel_id)
        
        