import logging
from pathlib import Path

logger = logging.getLogger(__name__)

import numpy as np

try:
    import scipy
    import scipy.ndimage
    HAS_SCIPY = True

except:
    HAS_SCIPY = False

from ...panels import CheckMenu
from ... import config, gui

from .demosaic import bayer_split
from .blueprint import make_thumbnail

respath = Path(config['respath'])

class ProcessMenu(CheckMenu):

    def __init__(self, name, parentMenu=None, basePanel=None):
        super().__init__(name, parentMenu)
        
        self.basePanel = basePanel   
        
        basePanel.addMenuItem(self, 'Bayer Split', self.bayer_split_tiles,
            statusTip="Split to 4 images based on the Bayer kernel",
            icon = str(respath / 'icons' / 'px16' / 'pictures_thumbs.png'))
            
        basePanel.addMenuItem(self, 'Colored Bayer', self.colored_bayer)
        
        basePanel.addMenuItem(self, 'Demosaic', self.demosaic, enabled=HAS_SCIPY,
            statusTip="Demosaic",
            icon = str(respath / 'icons' / 'px16' / 'things_digital.png'))
            
        basePanel.addMenuItem(self, 'Make Blueprint', self.makeBlueprint,
            statusTip="Make a thumbnail (8x smaller) with blowup high frequencies",
            icon = str(respath / 'icons' / 'px16' / 'map_blue.png'))
            
            
    @property
    def ndarray(self):
        return self.basePanel.ndarray
                       
        
    def show_array(self, array):
        self.basePanel.show_array(array)                
			

    def bayer_split_tiles(self):
        arr = self.ndarray
        blocks = []
        for y, x in [(0,0),(0,1),(1,0),(1,1)]:
            blocks.append(arr[y::2, x::2, ...])
        split = np.concatenate([
            np.concatenate([blocks[0], blocks[1]], axis=1),
            np.concatenate([blocks[2], blocks[3]], axis=1)])
        self.show_array(split)


    def colored_bayer(self):
        baypatns = ['RGGB', 'BGGR', 'GRBG', 'GBRG']
        form = [('Bayer Pattern', [1] + baypatns)]
        ind = gui.fedit(form, title='Demosaic')[0]
        baypatn = baypatns[ind-1]

        procarr = bayer_split(self.ndarray, baypatn)
        self.show_array(procarr)


    def demosaic(self):
        baypatns = ['RGGB', 'BGGR', 'GRBG', 'GBRG']
        form = [('Bayer Pattern', [1] + baypatns)]
        ind = gui.fedit(form, title='Demosaic')[0]
        baypatn = baypatns[ind-1]

        code = f"""\
        from gdesk.panels.imgview.demosaic import demosaicing_CFA_Bayer_bilinear
        procarr = demosaicing_CFA_Bayer_bilinear(gui.vs, '{baypatn}')
        gui.show(procarr)"""

        panel = gui.qapp.panels.selected('console')
        panel.exec_cmd(code)


    def makeBlueprint(self):
        with gui.qapp.waitCursor('making blueprint'):
            arr = self.ndarray

            if arr.ndim == 3:
                dtype = arr.dtype
                arr = arr.mean(2).astype(dtype)

            blueprint = make_thumbnail(arr)
            gui.img.new()
            gui.img.show(blueprint)