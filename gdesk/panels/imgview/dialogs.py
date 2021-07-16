import logging
from pathlib import Path
from collections import OrderedDict

import numpy as np

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtCore import Qt

from ... import gui, config
from ...panels.base import BasePanel, CheckMenu
from ...dialogs.formlayout import fedit
from ...utils import get_factors

logger = logging.getLogger(__name__)
respath = Path(config['respath'])                      
        
class RawImportForm(QtWidgets.QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)        
        
        vbox = QtWidgets.QVBoxLayout()
        vbox.setContentsMargins(5, 5, 5, 5)
        vbox.setMargin(5)
        self.setLayout(vbox)
        
        flay = QtWidgets.QFormLayout()
        vbox.addLayout(flay)         
        
        self.offset = QtWidgets.QLineEdit()
        flay.addRow('Offset', self.offset)
        
        self.dtype = QtWidgets.QLineEdit()
        flay.addRow('Data type', self.dtype) 
        
        self.byteorder = QtWidgets.QComboBox()
        self.byteorder.addItem('litle endian')
        self.byteorder.addItem('big endian')     
        flay.addRow('Byte Order', self.byteorder) 
        
        self.guess = QtWidgets.QPushButton('Resolutions')
        self.guess.clicked.connect(self.guessSize)
        flay.addRow('Guess size', self.guess)            
        
        self.width = QtWidgets.QLineEdit()
        flay.addRow('Width', self.width)             
        
        self.height = QtWidgets.QLineEdit()
        flay.addRow('Height', self.height)        

    def guessSize(self):
        flatsize = len(self.parent().data)
        flatsize = flatsize - int(self.offset.text())
        flatsize /= np.dtype(self.dtype.text()).itemsize
        
        factors = get_factors(flatsize)
        
        ratios = {}
        for width in factors:
            height = flatsize // width
            ratios[width/height] = [int(width), int(height)]
        
        sorted_ratios = sorted(ratios)
        resolutions = [' x '.join(str(v) for v in ratios[ratio]) for ratio in sorted_ratios]

        options_form = [('Resolutions', [len(factors) // 2] + resolutions)]                      
        choosen = fedit(options_form)[0] - 1
        width, height = ratios[sorted_ratios[choosen]]            
        
        #height, width = get_factors_equal(flatsize, 2)
        self.height.setText(str(height))
        self.width.setText(str(width))
        
class RawImportDialog(QtWidgets.QDialog):

    def __init__(self, data):
        super().__init__()
        self.data = data
        self.initUI()
        
    def initUI(self):
        self.form = RawImportForm(self)
        self.buttonOk = QtWidgets.QPushButton('Ok', self)
        self.buttonCancel = QtWidgets.QPushButton('Cancel', self)
        
        vbox = QtWidgets.QVBoxLayout()        
        self.setLayout(vbox)
        
        vbox.addWidget(self.form)              

        bhbox = QtWidgets.QHBoxLayout()
        bhbox.addStretch()
        bhbox.addWidget(self.buttonOk)
        bhbox.addWidget(self.buttonCancel)

        vbox.addLayout(bhbox)
        self.setLayout(vbox)

        self.connect(self.buttonOk, QtCore.SIGNAL('clicked()'), self.accept)
        self.connect(self.buttonCancel, QtCore.SIGNAL('clicked()'), self.reject)        
        
        self.show()
            