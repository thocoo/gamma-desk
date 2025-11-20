import pathlib
import numpy as np
from scipy import special

from qtpy import QtCore, QtGui, QtWidgets

from ... import config, gui

from ...graphics.view import SceneView
from ...graphics.items import createCurve, Indicator
from ...graphics.rulers import TickedRuler, Grid
from ..base import BasePanel, CheckMenu


RESPATH = pathlib.Path(config['respath'])

COLORS = {
    'K': QtGui.QColor(0, 0, 0),
    'roi.K': QtGui.QColor(255, 0, 0),
    'R': QtGui.QColor(255, 0, 0),
    'G': QtGui.QColor(0, 255, 0),
    'Gr': QtGui.QColor(0x80, 0x80, 0),
    'Gb': QtGui.QColor(0, 0x80, 0x80),
    'B': QtGui.QColor(0, 0, 255),
    'roi.R': QtGui.QColor(192, 0, 0),
    'roi.G': QtGui.QColor(64, 127, 0),
    'roi.Gr': QtGui.QColor(0x40, 0x80, 0),
    'roi.Gb': QtGui.QColor(0, 0x80, 0x40),
    'roi.B': QtGui.QColor(64, 0, 127)}    
    
    
def semilog(vec):
    with np.errstate(divide='ignore'):
        result = np.nan_to_num(np.log10(vec), neginf=-1) + 1
    return result
    

def scaleErfInvNorm(norm_values):
    # Values expected from 0 to 1
    clipped = np.clip(norm_values * 2 - 1, -0.999_999_999, 0.999_999_999)
    return special.erfinv(clipped)    


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
        
        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(0,0,0,0)
        self.vbox.addWidget(self.view)
        self.setLayout(self.vbox)
        
        self.create_x_ruler()
        self.create_y_ruler()      
        
        self.indicators = []
        
        self.create_indicator(0, QtGui.QColor(0,0,127), 'B:%0.5g', self.IndicatorBMoved)                        
        self.create_indicator(256, QtGui.QColor(255,127,127), 'W:%0.5g', self.IndicatorWMoved)        
        
        self.curves = dict()                      
        self.plot_curve('K', np.array([0, 0, 64, 64, 128, 128, 192, 192, 256, 256]), np.array([0, 1, 1, 0, 0, 2, 2, 1, 1, 0]))
        
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
        
        self.zoomFull()

    def create_indicator(self, xpos, color, text = None, slot=None):
        indicator = Indicator(color, text, parent=self.x_ruler)
        indicator.setPos(xpos, 0)
        indicator.setZValue(2.0)
        indicator.mouse_released.connect(slot)
        self.indicators.append(indicator)
        
        
    def set_logscale(self, enable=False):    
        for ind in self.indicators:
            ind.logscale = enable
            
        self.y_ruler.logscale = enable
            
        
    def create_x_ruler(self):
        x0, y0, x1, y1 = self.view.viewRectCoord()
        self.x_ruler = TickedRuler(0, x0, x1, abs(self.view.scale[0]),
                                   bg_color=self.palette().color(QtGui.QPalette.Base), noDecimals=False, parent=None)
        self.v_grid = Grid(self.x_ruler,  parent=None)
        self.x_ruler.setPos(0, y0 - self.view.pixelSize()[1] * 22)     
        self.v_grid.setPos(0, y0 - self.view.pixelSize()[1] * 22)     
        self.x_ruler.setZValue(1.0)
        self.v_grid.setZValue(-1)
        self.scene.addItem(self.x_ruler)              
        self.scene.addItem(self.v_grid)
        
    def create_y_ruler(self):
        x0, y0, x1, y1 = self.view.viewRectCoord()
        self.y_ruler = TickedRuler(-90, y0, y1, abs(self.view.scale[1]),
                                   bg_color=self.palette().color(QtGui.QPalette.Base), noDecimals=False)
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
        self.xmin = x0 + self.view.pixelSize()[0] * 22
        self.xmax = x1     
        
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
        
    def plot_curve(self, curveid=None, x=[], y=[], color = None, fill=50, dim=False, zero_ends=True):
        oldcolor = None
        
        if curveid in self.curves.keys():
            oldcurve = self.curves[curveid]
            oldcolor = oldcurve.pen().color()
            self.scene.removeItem(oldcurve)
            
        elif curveid is None:            
            curveid = len(self.curves)            

        if color is None:
            if oldcolor is None:
                color = COLORS[curveid]
            else:
                color = oldcolor
            
        curve = createCurve(x, y, color = color, fill=fill, zero_ends=zero_ends)        
        
        if dim:
            curve.setZValue(0)
            curve.setOpacity(0.25)
            
        else:
            curve.setZValue(0.5)            
        
        self.curves[curveid] = curve                     
        self.scene.addItem(curve)
        
        return curveid
        
        
    def toggleYlabels(self):
        for ind in self.indicators:
            ind.show_ylabels = not ind.show_ylabels 
            ind.updates_ylabels()
        
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
        
        x0 = self.indicators[0].pos().x()
        x1 = self.indicators[1].pos().x()                
        
        ymin_cand = ymax_cand = None

        for curve in self.curves.values():            
            xvec = curve.xvector
            yvec = curve.yvector
            indices = np.argwhere((x0 <= xvec) & (xvec < x1))
            if len(indices) > 0:
                yvecclip = yvec[indices]
            else:
                yvecclip = yvec
            ymin_chan = min(yvecclip)
            ymax_chan= max(yvecclip)            
            if (ymin_cand is None) or (ymin_chan < ymin_cand):
                ymin_cand = ymin_chan
            if (ymax_cand is None) or (ymax_chan > ymax_cand):
                ymax_cand = ymax_chan    

        ymin_cand = ymin if not ymin is None else ymin_cand

        if not ymin_cand is None and not ymax_cand is None and ymin_cand < ymax_cand:
            self.ymin = ymin_cand
            self.ymax = ymax_cand  
            
        else:
            return

        self.view.setYLimits(self.ymin, self.ymax, 22, 0)
        self.update_rulers(True, True)
        
    def zoomBetweenIndicators(self, skip_if_visible=False):
        x0 = self.indicators[0].pos().x()
        x1 = self.indicators[1].pos().x()
        if skip_if_visible:
            cx0, cy0, cx1, cy1 = self.view.viewRectCoord()
            x0 = min(x0, cx0 + 22 / self.view.scale[0])
            #x0 = min(x0, cx0 + 22)
            x1 = max(x1, cx1)
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
        self.view.setXLimits(self.xmin, self.xmax, 22, 0)
        self.update_rulers(True, True)       


    def selectCurves(self, curveNames):
    
        for name, curve in self.curves.items():
            if len(curveNames) == 0  or (name in curveNames):
                curve.setZValue(0.5)
                curve.setOpacity(1)
                
            else:
                curve.setOpacity(0.25)
                curve.setZValue(0)
        
        self.view.refresh()              

       
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
        self.updateHistOfPanel(None)
            
    def updateHistOfPanel(self, panelId=None):
        self.updatedCachedHistogram(panelId)                
            
        if self.panel.fitheight:           
            self.zoomFitYRange()

    def updatedCachedHistogram(self, panid):      
        image_panel = self.image_panel(panid)
        
        chanstats = image_panel.imviewer.imgdata.chanstats 
        #masks = image_panel.imviewer.imgdata.masks 
        
        if self.panel.histSizePolicy == 'bins':
            bins = int(self.panel.histSize)               
        else:
            bins = None
            step = self.panel.histSize        
        
        clr_to_draw = [m for m, chanstat in chanstats.items() if chanstat.is_valid() and chanstat.active and chanstat.hist_visible]  
        
        self.levelplot.remove_all_but(clr_to_draw)
        
        for clr in clr_to_draw: 
            chanstat = chanstats[clr]        
            
            color = chanstat.plot_color
            dim = chanstat.dim
            
            if len(chanstat._cache.keys()) == 0:
                chanstat.calc_histogram()            
            
            if bins is None:                
                stepmult = round(step / chanstat._cache['stepsize'])
                stepmult = max(1, stepmult)                
            else:
                stepmult = chanstat.step_for_bins(bins)
                                      
            hist = chanstat.histogram(stepmult)
            
            if self.panel.cummulative:
                hist = np.cumsum(hist)
                fill = 0
                zero_ends = False
            else:
                fill = 50
                zero_ends = True
            
            if self.panel.log: 
                if self.panel.cummulative:
                    hist = scaleErfInvNorm(hist / hist.max())
                    self.levelplot.view.freeze_y0 = False
                    
                else:
                    hist = semilog(hist)
                    self.levelplot.view.freeze_y0 = True
                
            elif self.panel.normalize:
                hist = hist / max(1, hist.max())
                self.levelplot.view.freeze_y0 = True
                
            else:
                self.levelplot.view.freeze_y0 = True
                
                
            starts = chanstat.starts(stepmult)   
            if len(starts) == 0: continue
            stepsize = chanstat.stepsize(stepmult)
            barstarts, histbar = self.xy_as_steps(starts, hist, stepsize)
            self.levelplot.plot_curve(clr, barstarts, histbar, color, dim=dim, fill=fill, zero_ends=zero_ends)
            
            if self.panel.gaussview:
                import scipy.signal
                
                std = chanstat.std()
                m =  chanstat.mean()
                npixel = chanstat.n()
                
                guass = scipy.signal.gaussian(len(starts), std= std / stepmult)
                offset = starts.mean() - m
                xvec = starts - offset
                yvec = guass * (npixel / guass.sum())
                
                if self.panel.log:
                    yvec = semilog(yvec)
                    
                xvec, yvec = self.xy_as_steps(xvec, yvec, stepsize)
                
                self.levelplot.plot_curve(f'{clr}_gv', xvec, yvec, color, fill=0)
                    
        self.levelplot.set_logscale(self.panel.log and not self.panel.cummulative)
        

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


    def toggleYlabels(self):
        self.levelplot.toggleYlabels()

            
    def indicZoom(self):
        self.levelplot.zoomBetweenIndicators()

        
    def bringIndicVisible(self, skip_if_visible=True):
        self.levelplot.zoomBetweenIndicators(skip_if_visible=skip_if_visible)

        
    def fullZoom(self):        
        ymin = None if (self.panel.cummulative and self.panel.log) else 0
        self.levelplot.zoomFull(enforce_ymin=ymin)    
        

    def zoomFitYRange(self):  
        ymin = None if (self.panel.cummulative and self.panel.log) else 0
        self.levelplot.zoomFitYRange(ymin=ymin)        


    def selectMasks(self, masks):
        self.levelplot.selectCurves(masks)
        
        
def enclose_func_args(func, *args, **kwargs):

    def enclosed():
        return func(*args, **kwargs)
        
    return enclosed
        
        

class LevelsToolBar(QtWidgets.QToolBar):

    selectMasks = QtCore.Signal(str)
    selectRoi = QtCore.Signal(str)    

    def __init__(self, *args, **kwargs):    
        super().__init__(*args, **kwargs) 
        self.initUi()

    @property
    def panel(self):
        return self.parent()       
        
    @property
    def levels(self):
        return self.parent().levels
        
    @property
    def stats(self):
        return self.parent().statPanel        
        
    def initUi(self):
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'update.png')), 'Refresh', self.levels.updateActiveHist)
        
        self.histSizePolicyBox = QtWidgets.QComboBox()
        self.histSizePolicyBox.addItem('bins')
        self.histSizePolicyBox.addItem('step')
        self.histSizePolicyBox.currentTextChanged.connect(self.histSizePolicyChanged)
        self.addWidget(self.histSizePolicyBox)        
        
        self.stepcount = QtWidgets.QLineEdit('64', self)
        self.stepcount.setMaximumWidth(100)
        self.stepcount.textChanged.connect(self.histSizeChanged)
        self.addWidget(self.stepcount)        

        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_fit.png')), 'Zoom to full histogram', self.levels.fullZoom)        
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_actual_equal.png')), 'Zoom Fit Y range', self.levels.zoomFitYRange)
        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'zoom_cursors.png')), 'Zoom to black white indicators', self.levels.indicZoom) 
        
        self.gainSigmaMenu = QtWidgets.QMenu('Contrast')
        
        actGainSigma1 = QtWidgets.QAction('Gain to Sigma 1', self, triggered=lambda: self.panel.autoContrast(1))
        actGainSigma1.setText('1σ 68.27%')
        actGainSigma1.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast_high.png')))        
        self.gainSigmaMenu.addAction(actGainSigma1)    
        
        actGainSigma2 = QtWidgets.QAction('Gain to Sigma 2', self, triggered=lambda: self.panel.autoContrast(2))
        actGainSigma2.setText('2σ 95.45%')
        actGainSigma2.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast.png')))        
        self.gainSigmaMenu.addAction(actGainSigma2)    
        
        actGainSigma3 = QtWidgets.QAction('Gain to Sigma 3', self, triggered=lambda: self.panel.autoContrast(3))
        actGainSigma3.setText('3σ 99.73%')
        actGainSigma3.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast_low.png')))        
        self.gainSigmaMenu.addAction(actGainSigma3)       
        
        actGainSigma4 = QtWidgets.QAction('Gain to Sigma 4', self, triggered=lambda: self.panel.autoContrast(4))
        actGainSigma4.setText('4σ 99.99%')
        actGainSigma4.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast_low.png')))        
        self.gainSigmaMenu.addAction(actGainSigma4)                   
                
        for word in [8, 10, 12, 14, 16, 20, 22, 24]:
            actGain = QtWidgets.QAction(f'{word} bit', self, triggered=enclose_func_args(self.panel.autoContrast, None, word))
            actGain.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_adjustment.png')))        
            self.gainSigmaMenu.addAction(actGain)          
        
        self.autoBtn = QtWidgets.QToolButton(self)
        self.autoBtn.setText(f'{self.panel.sigma}σ')
        self.autoBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast.png')))        
        self.autoBtn.setToolTip('Auto contrast to a certain sigma')
        self.autoBtn.setMenu(self.gainSigmaMenu)
        self.autoBtn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        self.autoBtn.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        self.autoBtn.clicked.connect(lambda: self.panel.autoContrast())        
        self.addWidget(self.autoBtn)
        
        self.applyUnityBtn = QtWidgets.QToolButton(self)
        self.applyUnityBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast_decrease.png')))
        self.applyUnityBtn.setToolTip('Apply default offset, gain and gamma')
        self.applyUnityBtn.clicked.connect(self.panel.gain1)
        self.addWidget(self.applyUnityBtn)                
                
        self.asUnityBtn = QtWidgets.QToolButton(self)
        self.asUnityBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast_increase.png')))
        self.asUnityBtn.setToolTip('Set current offset, gain and gamma as default')
        self.asUnityBtn.clicked.connect(self.panel.asUnity)
        self.addWidget(self.asUnityBtn)           
        
        self.eyeBtn = QtWidgets.QToolButton()
        self.eyeBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'layers_map.png')))      
        self.eyeBtn.setToolTip('Masks visibility in statastics, profiles and levels')
        self.eyeBtn.clicked.connect(lambda: self.selectRoi.emit('custom visibility'))                  
        self.addWidget(self.eyeBtn)
        
        self.masksSelectMenu = QtWidgets.QMenu('Select Masks')
        #self.masksSelectMenu.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_by_color.png')))      
        self.masksSelectMenu.addAction(QtWidgets.QAction("mono", self, triggered=lambda: self.selectMasks.emit('mono'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_gradient.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("rgb",  self, triggered=lambda: self.selectMasks.emit('rgb'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("bg",   self, triggered=lambda: self.selectMasks.emit('bg'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_bg.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("gb",   self, triggered=lambda: self.selectMasks.emit('gb'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_gb.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("rg",   self, triggered=lambda: self.selectMasks.emit('rg'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_rg.png'))))
        self.masksSelectMenu.addAction(QtWidgets.QAction("gr",   self, triggered=lambda: self.selectMasks.emit('gr'), icon=QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cfa_gr.png'))))
        
        self.masksSelectBtn = QtWidgets.QToolButton()
        self.masksSelectBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'select_by_color.png')))      
        self.masksSelectBtn.setToolTip('Select one of the default masks options')
        self.masksSelectBtn.setMenu(self.masksSelectMenu)
        self.masksSelectBtn.setPopupMode(QtWidgets.QToolButton.InstantPopup)          
        
        self.addWidget(self.masksSelectBtn)             

        self.scaleBtn = QtWidgets.QToolButton(self)
        self.scaleBtn.setText('lin')
        self.scaleBtn.clicked.connect(self.nextScale)
        self.scaleBtn.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)
        
        self.scaleMenu = QtWidgets.QMenu('Scale')
        linearScale = QtWidgets.QAction(f'Linear', self, triggered=lambda: self.setScale('lin'))
        linearScale.setToolTip('Use Linear Y-scale')
        logScale = QtWidgets.QAction(f'Log', self, triggered=lambda: self.setScale('log'))        
        logScale.setToolTip('Use Logaritmic Y-scale')
        normScale = QtWidgets.QAction(f'Normalized', self, triggered=lambda: self.setScale('norm'))
        normScale.setToolTip('Use Normalized scale')
        self.scaleMenu.addAction(linearScale)
        self.scaleMenu.addAction(logScale)
        self.scaleMenu.addAction(normScale)
        self.scaleBtn.setMenu(self.scaleMenu) 
        self.addWidget(self.scaleBtn)
        
        self.cummBtn = QtWidgets.QToolButton(self)
        self.cummBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'sum.png')))
        self.cummBtn.setCheckable(True)
        self.cummBtn.setToolTip('Cummulative')
        self.cummBtn.clicked.connect(self.toggleCummulative)
        self.addWidget(self.cummBtn)
        checkable_style = "QToolButton:checked {background-color: lightblue; border: none;}"
        self.cummBtn.setStyleSheet(checkable_style)
        
        self.yLabelBtn = QtWidgets.QToolButton(self)
        self.yLabelBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'tag_hash.png')))
        self.yLabelBtn.clicked.connect(self.panel.levels.toggleYlabels)
        self.addWidget(self.yLabelBtn)

        self.addAction(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'dopplr.png')), 'Choose colormap', self.colorMap)        
        
        fontHeight = self.fontMetrics().height()
        self.setIconSize(QtCore.QSize(int(fontHeight * 3 / 2), int(fontHeight * 3 / 2)))
        
    def histSizePolicyChanged(self, text):
        self.stepcount.setText(str(self.panel.histSizes[text]))
        
    def histSizeChanged(self, text):
        histSizePolicy = self.histSizePolicyBox.currentText()
        self.panel.histSizePolicy = histSizePolicy
        self.panel.histSizes[histSizePolicy] = eval(text)
        
    def updateStepCount(self):
        self.stepcount.setText(str(self.panel.histSizes[self.histSizePolicyBox.currentText()]))        
        
    # def toggleRoi(self):
        # sender = self.sender()
        # self.panel.roi = sender.isChecked()
        # self.levels.updateActiveHist()
        
    def toggleLogNorm(self):
        self.panel.log = self.logBtn.isChecked()
        self.panel.normalize = self.normBtn.isChecked()
        self.levels.updateActiveHist()
        
        
    def nextScale(self):
        current_scale = self.scaleBtn.text()        
        scales = ['lin', 'log', 'norm']
        next_scale = scales[(scales.index(current_scale) + 1) % 3]
        self.setScale(next_scale)
        
        
    def setScale(self, scale):
        self.scaleBtn.setText(scale)
        
        if scale == 'lin':
            self.panel.log = False
            self.panel.normalize = False
            
        elif scale == 'log':
            self.panel.log = True
            self.panel.normalize = False
            
        elif scale == 'norm':
            self.panel.log = False
            self.panel.normalize = True
            
        self.levels.updateActiveHist()  
        
          
    def toggleCummulative(self):
        self.panel.cummulative = self.cummBtn.isChecked()
        self.levels.updateActiveHist()     
        
    def updateButtonStates(self):
        self.histSizePolicyBox.setCurrentText(self.panel.histSizePolicy)
        #self.useRoiBtn.setChecked(self.panel.roi)
        
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
    
    classIconFile = str(RESPATH / 'icons' / 'px16' / 'color_adjustment.png')

    def __init__(self, parent, panid):    
        super().__init__(parent, panid, 'levels')  

        self.histSizePolicy = config['levels'].get('hist_size_policy', 'bins')
        bins = config['levels'].get('bins', 64)
        step = config['levels'].get('step', 4)
        self.histSizes = {'bins': bins, 'step': step}
        
        self.fitheight = True
        self.gaussview = False
        self.log = False
        #self.roi = False
        self.normalize = False
        self.cummulative = False
        
        self.sigma = 3
        
        self.levels = Levels(self)
        self.setCentralWidget(self.levels)
        
        self.toolbar = LevelsToolBar(self)
        self.addToolBar(self.toolbar)           
        
        self.fileMenu = self.menuBar().addMenu("&File")
        self.modeMenu = CheckMenu("&Mode", self.menuBar())
        self.menuBar().addMenu(self.modeMenu)        
        
        self.addMenuItem(self.fileMenu, 'Close', self.close_panel,
            statusTip="Close this levels panel",
            icon = QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'cross.png')))
        
        self.addMenuItem(self.modeMenu, 'Fit Height', self.toggle_fitheight, checkcall=lambda: self.fitheight)
        self.addMenuItem(self.modeMenu, 'Gaussian', self.toggle_gaussview, checkcall=lambda: self.gaussview)
        #self.addMenuItem(self.modeMenu, 'Roi', self.toggle_roi, checkcall=lambda: self.roi)
        self.addMenuItem(self.modeMenu, 'Log', self.toggle_log, checkcall=lambda: self.log)
        self.addMenuItem(self.modeMenu, 'Normalize', self.toggle_log, checkcall=lambda: self.normalize)
        self.addMenuItem(self.modeMenu, 'Cummulative', self.toggle_cumm, checkcall=lambda: self.cummulative)
        
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
        
        #selectMasks = QtCore.Signal(str)
        #selectRoi = QtCore.Signal(str) 
        self.toolbar.selectMasks.connect(targetPanel.imgprof.selectMasks)
        self.toolbar.selectRoi.connect(targetPanel.imgprof.selectRoi)
        
        return targetPanel
        
    def removeBindingTo(self, category, panid):
        targetPanel = super().removeBindingTo(category, panid)
        if targetPanel is None: return None
        self.offsetGainChanged.disconnect(targetPanel.changeOffsetGain)        
        self.blackWhiteChanged.disconnect(targetPanel.changeBlackWhite)        
        return targetPanel         
        
    def toggle_fitheight(self):
        self.fitheight= not self.fitheight
        self.toolbar.updateButtonStates()
        self.levels.updateActiveHist()        
        
    def toggle_gaussview(self):
        self.gaussview = not self.gaussview
        self.toolbar.updateButtonStates()
        self.levels.updateActiveHist()        
        
    # def toggle_roi(self):
        # self.roi = not self.roi
        # self.toolbar.updateButtonStates()
        # self.levels.updateActiveHist()        

    def toggle_log(self):
        self.log = not self.log
        self.toolbar.updateButtonStates()
        self.levels.updateActiveHist()   

    def toggle_normalize(self):
        self.normalize = not self.normalize
        self.toolbar.updateButtonStates()
        self.levels.updateActiveHist()          
        
    def toggle_cumm(self):
        self.cummulative = not self.cummulative
        

    def toggle_stats(self):
        self.stats = not self.stats
        if self.stats:
            self.statDock.show()
        else:
            self.statDock.hide()
        
    def autoContrast(self, sigma=None, bits=None):
        if not sigma is None:
            self.sigma = sigma
            self.toolbar.autoBtn.setText(f'{sigma}σ')
            self.toolbar.autoBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'contrast.png')))       
            
        if not bits is None:
            self.bits = bits
            self.toolbar.autoBtn.setText(f'{bits} bit')            
            self.toolbar.autoBtn.setIcon(QtGui.QIcon(str(RESPATH / 'icons' / 'px16' / 'color_adjustment.png')))
            
        for panel in self.targetPanels('image'):
            text = self.toolbar.autoBtn.text()
            
            if not sigma is None or 'σ' in text:
                #panel.gainToSigma(self.sigma, self.roi)             
                panel.gainToSigma(self.sigma)             
            
            elif not bits is None or 'bit' in text:
                panel.changeBlackWhite(0, 2**self.bits)      
            
        if not sigma is None:            
            self.levels.bringIndicVisible(skip_if_visible=True)
          
        if not bits is None:          
            self.levels.bringIndicVisible(skip_if_visible=False)

    def setHistSizePolicy(self, size_policy: str, count: int):
        """
        Configure the higtogram bin size.

        :param size_policy: Either 'bins' or 'step'.
        :param count: Number of bins to use, or the step size in number of bits.
        """
        assert size_policy in ["bins", "step"]
        assert isinstance(count, int)
        self.toolbar.histSizePolicyBox.setCurrentText(size_policy)
        self.toolbar.stepcount.setText(str(count))

    def setScale(self, scale_name: str):
        """
        Configure the vertical scale of the histogram.

        :param scale_name: Either 'lin', 'log' or 'norm'.
        """
        assert scale_name in ["lin", "log", "norm"]
        self.toolbar.setScale(scale_name)

    def gain1(self):
        #self.offsetGainChanged.emit('default', 'default', 'default')
        for panel in self.targetPanels('image'):
            panel.changeOffsetGain('default', 'default', 'default', True)
        #self.levels.indicZoom()
        
    def updateBlackPoint(self, value):
        #self.blackWhiteChanged.emit(value, None)
        for panel in self.targetPanels('image'):
            panel.changeBlackWhite(value, None)        
        
    def updateWhitePoint(self, value):
        #self.blackWhiteChanged.emit(None, value)
        for panel in self.targetPanels('image'):
            panel.changeBlackWhite(None, value) 

    def asUnity(self):
        for panel in self.targetPanels('image'):
            panel.setCurrentOffsetGainAsDefault()
        
    def imageContentChanged(self, image_panel_id, zoomFit=False):
        if self.levels.isVisible():
            self.levels.updateHistOfPanel(image_panel_id)        
            
        if zoomFit:
            self.levels.fullZoom()

    def imageGainChanged(self, image_panel_id, zoomDefault=False):
        self.levels.updateIndicators(image_panel_id)      
        if zoomDefault:
            self.levels.indicZoom()
        
    def roiChanged(self, image_panel_id):
        self.levels.updateHistOfPanel(image_panel_id)

    def selectMasks(self, masks):
        if masks == '':
            masks = []
            
        else:
            masks = masks.split(',')    
        
        self.levels.selectMasks(masks)
