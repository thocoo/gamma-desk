from qtpy import QtCore, QtGui, QtOpenGL, QtWidgets
from .point import Point
from . import functions as fn

QtSignal = QtCore.Signal

HAVE_OPENGL = True

class PlotView(QtWidgets.QGraphicsView):

    """
    Re-implementation of QGraphicsView without scrollbars.

    Allow unambiguous control of the viewed coordinate range.
    """

    matrixUpdated = QtSignal()
    doubleClicked = QtSignal()
    
    scaleXUpdated = QtSignal()
    panXUpdated = QtSignal()
    scaleYUpdated = QtSignal()
    panYUpdated = QtSignal()

    def __init__(self, parent=None, background='default'):
        super().__init__(parent)

        # There is the experimental options of using OpenGl
        self.useOpenGL(False)
        self.setCacheMode(self.CacheBackground)
        self.setBackground(background)
        
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        #self.setResizeAnchor(QtWidgets.QGraphicsView.AnchorViewCenter)

        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        
        #self.setViewportUpdateMode(QtWidgets.QGraphicsView.MinimalViewportUpdate)
        self.setViewportUpdateMode(QtWidgets.QGraphicsView.NoViewportUpdate)
        
        #self.setStyleSheet( "QGraphicsView { border-style: none; }" )
        
        #self.setMouseTracking(True)
        
        #self.range = QtCore.QRectF(0, 0, 1, 1)
        self.scale = [100 / 2**16, 100 / 2**16]
        self.center = [2**15, 2**15]
        self.lastMousePos = None
        
        self.fixScaleX = False
        self.fixScaleY = False
        
        fullrange = QtCore.QRectF(-1e6, -1e6, 2e6, 2e6)
        self.setSceneRect(fullrange)
        self.updateMatrix()
        
        self.initMenu()
        
    @property
    def auto_zoom(self):
        """
        Check whether the 'Auto Zoom' checkbox is checked.

        :return bool: True when auto zoom is checked / enabled.
        """
        return self.autoAction.isChecked()
        
    def initMenu(self):  
        self.menu = QtWidgets.QMenu(self)
        
        self.autoAction = QtWidgets.QAction('Auto Zoom', self)
        self.autoAction.setCheckable(True)
        self.autoAction.setChecked(True)
        self.autoAction.triggered.connect(self.toggleAutoZoom)
        self.menu.addAction(self.autoAction)       
        
    def toggleAutoZoom(self):
        #just toggle the check boxs
        pass     
        
    def useOpenGL(self, b=True):
        if b:
            if not HAVE_OPENGL:
                raise Exception("Requested to use OpenGL with QGraphicsView, but QtOpenGL module is not available.")
            v = QtOpenGL.QGLWidget()
        else:
            v = QtWidgets.QWidget()
            
        self.setViewport(v)

    def setBackground(self, background):
        """
        Set the background color of the GraphicsView.
        To make the background transparent, use background=None.
        """
        self._background = background
        if background == 'default':
            background = (250, 250, 250)
        if background is None:
            self.setBackgroundRole(QtGui.QPalette.NoRole)
        else:
            brush = fn.mkBrush(background)
            self.setBackgroundBrush(brush)
        
    def updateMatrix(self, propagate=True):        
        #t = self.transform()
        self.limitRefreshRange()        
        self.setTransform(QtGui.QTransform(\
            self.scale[0], 0  , 0,\
            0  , self.scale[1], 0,\
            0  , 0  , 1))
        
        #self.ensureVisible(self.range,0,0)        
        self.centerOn(*self.center)       
        #self.setSceneRect(self.range)
        #self.fitInView(self.range, QtCore.Qt.IgnoreAspectRatio)                        
        self.matrixUpdated.emit()
        self.viewport().update()
        #self.updateSceneRect(self.range)
        
    def limitRefreshRange(self):
        self.range = QtCore.QRectF()
        self.range.setWidth((self.width() + 20)/ self.scale[0])
        self.range.setHeight((self.height() + 20) / self.scale[1])
        self.range.moveCenter(QtCore.QPointF(*self.center))        
        self.setSceneRect(self.range)    
               
    def translate(self, dx, dy):
        self.center = [self.center[0] +dx, self.center[1] + dy]
        self.updateMatrix()
        if dx != 0:
            self.panXUpdated.emit()
        if dy != 0:
            self.panYUpdated.emit()
            
    def setXCenter(self, pos):
        self.center[0] = pos
        
        self.limitRefreshRange()
        
        t = self.transform()
        self.setTransform(QtGui.QTransform(\
            self.scale[0], 0      , 0,\
            0    , t.m22(), 0,\
            0    , 0      , 1))                    
        self.centerOn(*self.center)
        
        self.scaleXUpdated.emit()
        self.panXUpdated.emit()
        self.matrixUpdated.emit()
        self.viewport().update()            
        
                
    def setXPosScale(self, pos, scale):
        if scale == 0:
            return
        self.scale[0] = scale
        self.center[0] = pos + self.width() / 2.0 / scale 
        
        self.limitRefreshRange()
        
        t = self.transform()
        self.setTransform(QtGui.QTransform(\
            scale, 0      , 0,\
            0    , t.m22(), 0,\
            0    , 0      , 1))                    
        self.centerOn(*self.center)
        
        self.scaleXUpdated.emit()
        self.panXUpdated.emit()
        self.matrixUpdated.emit()
        self.viewport().update()
        #self.updateSceneRect(self.range)
        
    def setYCenter(self, pos):
        self.center[1] = pos 
        
        self.limitRefreshRange()
        
        t = self.transform()
        self.setTransform(QtGui.QTransform(\
            t.m11(), 0    , 0,\
            0      , self.scale[1], 0,\
            0      , 0    , 1))                    
        self.centerOn(*self.center)
        
        self.scaleYUpdated.emit()
        self.panYUpdated.emit()
        self.matrixUpdated.emit()   
        self.viewport().update()        
        
        
    def setYPosScale(self, pos, scale):
        if scale == 0:
            return
        self.scale[1] = scale
        self.center[1] = pos + self.height() / 2.0 / scale 
        
        self.limitRefreshRange()
        
        t = self.transform()
        self.setTransform(QtGui.QTransform(\
            t.m11(), 0    , 0,\
            0      , scale, 0,\
            0      , 0    , 1))                    
        self.centerOn(*self.center)
        
        self.scaleYUpdated.emit()
        self.panYUpdated.emit()
        self.matrixUpdated.emit()   
        self.viewport().update()
        #self.updateSceneRect(self.range)        
        
    def refresh(self):
        self.viewport().update()
        
    def setScale(self, sx, sy):
        self.scale = [sx, sy]        
        self.updateMatrix()        

    def mousePressEvent(self, ev):
        #QtWidgets.QGraphicsView.mousePressEvent(self, ev)
        
        if (ev.buttons() == QtCore.Qt.LeftButton):
            self.lastMousePos = Point(ev.pos())
            self.mousePressPos = ev.pos()

        if (ev.buttons() == QtCore.Qt.RightButton):
            pos = QtGui.QCursor.pos()
            self.menu.exec_(pos)  
            
        self.clickAccepted = ev.isAccepted()                  
               
    def mouseMoveEvent(self, ev):
    
        if self.lastMousePos is None:
            self.lastMousePos = Point(ev.pos())
            
        delta = Point(ev.pos() - self.lastMousePos.toPoint())
        self.lastMousePos = Point(ev.pos())

        # QtWidgets.QGraphicsView.mouseMoveEvent(self, ev)
        
        if ev.buttons() in [QtCore.Qt.MidButton, QtCore.Qt.LeftButton]:  ## Allow panning by left or mid button.
            px = self.pixelSize()
            tr = -delta * px
            if self.fixScaleX:
                tr[0] = 0
            if self.fixScaleY:
                tr[1] = 0
            self.translate(tr[0], tr[1])
                
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
            
    def wheelEvent(self, ev):
        # QtWidgets.QGraphicsView.wheelEvent(self, ev)
        if not self.fixScaleX and not self.fixScaleY:
            self.scale[0] = self.scale[0] * 1.001 ** ev.delta()
            self.scale[1] = self.scale[1] * 1.001 ** ev.delta()
            self.updateMatrix()
            self.scaleXUpdated.emit()
            self.panXUpdated.emit()
            self.scaleYUpdated.emit()
            self.panYUpdated.emit()
        elif self.fixScaleX and not self.fixScaleY:                
                self.scale[1] = self.scale[1] * 1.001 ** ev.delta()
                self.updateMatrix()
                self.scaleXUpdated.emit()
                self.panXUpdated.emit()
        elif not self.fixScaleX and self.fixScaleY:                
                self.scale[0] = self.scale[0] * 1.001 ** ev.delta()        
                self.updateMatrix()
                self.scaleXUpdated.emit()
                self.panYUpdated.emit()

    def pixelSize(self):
        """Return vector with the length and width of one view pixel in scene coordinates"""
        p0 = Point(0,0)
        p1 = Point(1,1)
        tr = self.transform().inverted()[0]
        p01 = tr.map(p0)
        p11 = tr.map(p1)
        return Point(p11 - p01)
