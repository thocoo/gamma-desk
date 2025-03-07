"""multi-dim panel for image read, write and display support"""

import pathlib
import numpy as np

import imageio.v2
from qtpy import QtGui

from .hdf5 import load_ndim_from_hdf5, save_ndim_to_hdf5
from ... import config, gui

from gdesk.panels import BasePanel
from gdesk.panels.ndim.widget import NdimWidget

respath = pathlib.Path(config['respath'])

here = pathlib.Path(__file__).parent.absolute()


try:
    import h5py
    has_h5py = True
except ModuleNotFoundError:
    has_h5py = False


class NdimPanel(BasePanel):
    """Panel to handle multidimensional data of which two dimensions is image data

    Data can be loaded from code or from disk ising numpy (.npz), hdf5, GIF, ... files.
    imageio is used for all besides the hdf5 files.
    """
    panelCategory = 'ndim'
    panelShortName = 'basic'
    userVisible = True

    def __init__(self, parent, panid):
        super().__init__(parent, panid, self.panelCategory)
        self.main_widget = NdimWidget(self)
        self.setCentralWidget(self.main_widget)

        self.fileMenu = self.menuBar().addMenu("&File")
        self.addMenuItem(self.fileMenu, 'Open n-dim Array', self.open_dialog,
                         statusTip="Open a file containing n-dim data", icon='folder_image.png')
        self.addMenuItem(self.fileMenu, 'Save n-dim Array', self.save_dialog,
                         statusTip="Save the image", icon='picture_save.png')

        self.addMenuItem(self.fileMenu, 'Close', self.close_panel,
                         statusTip="Close this levels panel",
                         icon=QtGui.QIcon(str(respath / 'icons' / 'px16' / 'cross.png')))

        self.addBaseMenu(['image'])
        self.statusBar().hide()
        self._previous_folder = None

    def open_dialog(self):
        """Open file selection dialog and open the selected file"""
        if self._previous_folder is not None:
            filepath = self._previous_folder
        else:
            filepath = here.parent.parent / 'resources' / 'ndim' / 'space_cat.npz'

        filepath, filter = gui.getfile(title='Open n-dim data or multiple images', file=str(filepath.absolute()),
                                       filter="Supported (*.h5 *.hdf5 *.npz *.gif *.mov *.mp4);;"
                                              "hdf5 (*.h5 *.hdf5);;Numpy (*.npz);;GIF (*.gif);;MOV (*.mov);;"
                                              "MP4 (*.mp4);; All (*.*)")
        if filepath == '':
            return

        self._previous_folder = pathlib.Path(filepath).parent

        self.open(filepath)

    def save_dialog(self):
        """Open file selection dialog and save the data to the selected file"""
        filepath, filter = gui.putfile(title='Save n-dim data',
                                       filter="Supported (*.h5 *.hdf5 *.npz *.gif *.mov *.mp4);;"
                                              "hdf5 (*.h5 *.hdf5);;Numpy (*.npz);;GIF (*.gif);;MOV (*.mov);;"
                                              "MP4 (*.mp4);; All (*.*)")
        if filepath == '':
            return
        self.save(filepath, **self.main_widget.get_save_data())

    def open(self, filepath):
        """Open the file and load the data"""
        filepath = pathlib.Path(filepath)
        if filepath.suffix.lower() in (".h5", ".hdf5", ".he5"):
            data, name, dim_names, dim_scales = load_ndim_from_hdf5(filepath)
            self.load(data, name=name, dim_names=dim_names, dim_scales=dim_scales)
        else:
            data = np.array(imageio.v2.mimread(filepath))
            self.load(data)

    def save(self, filepath, data, data_name=None, dim_names=None, dim_scales=None):
        """Save the data to the filepath

        data_name, dim_names and dim_scales are only used when saving to hdf5

        :param filepath: path to save to
        :param data: numpy nd array with the multi dim data
        :param name: optional name of this data, is used when saving to hdf5
        :param dim_names: optional list of length ndim with names per dimensions
        :param dim_scales: optional list with (name, scale) tuples with scale values for each entry in a dim
        :return: None
        """
        filepath = pathlib.Path(filepath)
        if filepath.suffix.lower() in (".h5", ".hdf5", ".he5"):
            save_ndim_to_hdf5(filepath=filepath, data=data, data_name=data_name,
                              dim_names=dim_names, dim_scales=dim_scales)
        else:
            imageio.v2.mimsave(filepath, [im for im in data])

    def load(self, data, name=None, dim_names=None, dim_scales=None):
        """Load the data

        :param data: numpy nd array with the multi dim data
        :param name: optional name of this data, is used when saving to hdf5
        :param dim_names: optional list of length ndim with names per dimensions
        :param dim_scales: optional list with (name, scale) tuples with scale values for each entry in a dim
        :return: None
        """
        self.main_widget.load(data, name=name, dim_names=dim_names, dim_scales=dim_scales)

    def update_data(self, data):
        """ Update the current data iso doing a complete new load

        If the data does not have the same shape then load is called anyway
        :param data: numpy nd array to update
        :return: None
        """
        self.main_widget.update_data(data)

    def collapse(self, collapse):
        """Set the window collapsed or not when docked in a vertical way with other windows"""
        if collapse != self.parent().parent().collapsed:
            self.parent().parent().collapseVertical()
