from qtpy import QtCore, QtGui, QtWidgets

QtSignal = QtCore.Signal

from .point import Point

#Point = QtCore.QPointF

class SceneView(QtWidgets.QGraphicsView):

    scaled = QtSignal(bool, bool)
    scale_ended = QtSignal(bool, bool)
    translated = QtSignal(bool, bool)
    translate_ended = QtSignal(bool, bool)
    zoom_full = QtSignal()
    
    def __init__(self, parent):
        super().__init__(parent)
        #self.setMouseTracking(True)
        #self.setInteractive(False)  
        
        #self.useOpenGL(True)
        
        self.setCacheMode(self.CacheBackground)
        
        self.scale = [1, 1]
        self.center = [0, 0]
        
        self.fixScaleX = False
        self.fixScaleY = False
        
        self.lastMousePos = None        
        
        self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.setFocusPolicy(QtCore.Qt.StrongFocus)        
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.setTransformationAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setResizeAnchor(QtWidgets.QGraphicsView.NoAnchor)
        self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)        
        
        self.freeze_y0 = False
        self.old_view_rect = None
        
        # self.restore_view_rect_timer = QtCore.QTimer()
        # self.restore_view_rect_timer.timeout.connect(self.restore_view_rect)
        # self.restore_view_rect_timer.setSingleShot(True)        
        
        self.updateMatrix()

    def useOpenGL(self, b=True):
        if b:
            from PySide2 import QtOpenGL
            v = QtOpenGL.QGLWidget()
        else:
            v = QtWidgets.QWidget()
            
        self.setViewport(v)       

    # def restore_view_rect(self):
        # x0, y0, x1, y1 = self.old_view_rect
        # self.setXLimits(x0, x1, 0,0)
        # self.setYLimits(y0, y1, 0,0)
        # self.old_view_rect = None
        # self.scaled.emit(True, True)
        
    def setRange(self, scene_width, scene_height):
        self.scale[0] = self.width() / scene_width
        self.scale[1] = self.height() / scene_height
        self.updateMatrix()
        
    def updateMatrix(self, propagate=True):        
        #t = self.transform()
        self.limitRefreshRange()        
        self.setTransform(QtGui.QTransform(\
            self.scale[0], 0  , 0,\
            0  , self.scale[1], 0,\
            0  , 0  , 1))
                
        self.centerOn(*self.center)       
        self.viewport().update()

    def translate(self, dx, dy):
        self.center = [self.center[0] +dx, self.center[1] + dy]
        self.updateMatrix()     
        
    def limitRefreshRange(self):
        self.range = QtCore.QRectF()
        self.range.setWidth((self.width() + 20)/ self.scale[0])
        self.range.setHeight((self.height() + 20) / self.scale[1])
        self.range.moveCenter(QtCore.QPointF(*self.center))        
        self.setSceneRect(self.range)          

    def setXPosScale(self, pos, scale):
        self.scale[0] = scale
        self.center[0] = pos + self.width() / 2.0 / scale 
        
        self.limitRefreshRange()
        
        t = self.transform()
        self.setTransform(QtGui.QTransform(\
            scale, 0      , 0,\
            0    , t.m22(), 0,\
            0    , 0      , 1))                    
        self.centerOn(*self.center)       
        
    def setXLimits(self, low, high, left_border=0, right_border=0):
        self.scale[0] = (self.width() - left_border - right_border)/ (high - low)
        self.center[0] = (low - left_border / self.scale[0] + high) / 2 
        
        self.limitRefreshRange()
        self.updateMatrix()              

    def setYPosScale(self, pos, scale):
        self.scale[1] = scale
        self.center[1] = pos + self.height() / 2.0 / scale 
        
        self.limitRefreshRange()
        
        t = self.transform()
        self.setTransform(QtGui.QTransform(\
            t.m11(), 0    , 0,\
            0      , scale, 0,\
            0      , 0    , 1))                    
        self.centerOn(*self.center)  
        
    def setYLimits(self, low, high, bottom_border=0, top_border=0):
        self.scale[1] = (self.height() - bottom_border - top_border) / (low - high)
        self.center[1] = (low + bottom_border / self.scale[1] + high) / 2 
        
        self.limitRefreshRange()
        self.updateMatrix()            

    def wheelEvent(self, event):        
        wheel_delta = event.angleDelta().y()
        
        if not self.fixScaleX and (self.fixScaleY or self.freeze_y0):                
            self.scale[0] = self.scale[0] * 1.001 ** wheel_delta        
            self.updateMatrix()  
            self.scale_ended.emit(True, False)
                
        elif self.fixScaleX and not self.fixScaleY:                
            self.scale[1] = self.scale[1] * 1.001 ** wheel_delta
            self.updateMatrix()
            self.scale_ended.emit(False, True)                
                
        else:
            self.scale[0] = self.scale[0] * 1.001 ** wheel_delta
            self.scale[1] = self.scale[1] * 1.001 ** wheel_delta
            self.updateMatrix()
            self.scale_ended.emit(True, True)
    
    def pixelSize(self):
        """Return vector with the length and width of one view pixel in scene coordinates"""
        p0 = Point(0,0)
        p1 = Point(1,1)
        tr = self.transform().inverted()[0]
        p01 = tr.map(p0)
        p11 = tr.map(p1)
        return Point(p11 - p01) 

    def mousePressEvent(self, ev):    
        self.lastMousePos = Point(ev.pos())
        self.lastPressButton = ev.button()
        super().mousePressEvent(ev)
        #print('mouse press x:%d y:%d' % (self.lastMousePos[0], self.lastMousePos[1]))
        
    def mouseDoubleClickEvent(self, ev):            
        self.zoom_full.emit()
               
    def mouseMoveEvent(self, ev):               
        super().mouseMoveEvent(ev)
        
        if hasattr(self.scene(), 'moving_indicators') and self.scene().moving_indicators:
            self.scene().moving_indicators = False
            return
        
        if self.lastMousePos is None:
            self.lastMousePos = Point(ev.pos())
            
        delta = Point(ev.pos()) - self.lastMousePos
        self.lastMousePos = Point(ev.pos())
        
        if ev.buttons() in [QtCore.Qt.LeftButton]:
        #if ev.buttons() in [QtCore.Qt.MidButton, QtCore.Qt.RightButton]: 
            px = self.pixelSize()
            tr = -delta * px
            movex, movey = True, True
            if self.fixScaleX:
                tr[0] = 0
                movex = False
            if self.fixScaleY or self.freeze_y0:
                tr[1] = 0
                movey = False
            self.translate(tr[0], tr[1])   
            self.translated.emit(movex, movey)
        elif ev.buttons() in [QtCore.Qt.RightButton]:
            if not self.freeze_y0:
                px = self.pixelSize()
                self.scale[0] = self.scale[0] * 1.01 ** delta[0]
                self.scale[1] = self.scale[1] * 1.01 ** delta[1]
                self.updateMatrix()
                self.scaled.emit(True, True)
            elif self.freeze_y0:
                scale_x = 1.01 ** (-delta[0])
                scale_y = 1.01 ** delta[1]
                x0, y0, x1, y1 = self.viewRectCoord()
                
                cx = (x1 + x0) / 2
                rx = (x1 - x0) / 2
                x0 = cx - rx * scale_x
                x1 = cx + rx * scale_x
                self.setXLimits(x0, x1, 0, 0)
                
                y0 = y0 * scale_y
                y1 = y1 * scale_y                
                self.setYLimits(y0, y1, 0, 0)                
                
                self.scaled.emit(True, True)
        
    def viewRectCoord(self):
        #return the currently visible window in view coord
        xc, yc = self.center
        x0 = xc - self.width() / abs(self.scale[0]) / 2
        y0 = yc - self.height() / abs(self.scale[1]) / 2
        x1 = xc + self.width() / abs(self.scale[0]) / 2
        y1 = yc + self.height() / abs(self.scale[1]) / 2
        return x0, y0, x1, y1

    def refresh(self):
        self.viewport().update()
        
    def resizeEvent(self, ev):
        # if self.old_view_rect is None:
            # self.old_view_rect = x0, y0, x1, y1 = self.viewRectCoord()
            # self.restore_view_rect_timer.start(500)        
        self.updateMatrix()