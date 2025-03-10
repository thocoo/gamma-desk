from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from ...core.gui_proxy import GuiProxyBase, StaticGuiCall
from ... import gui


class NdimGuiProxy(GuiProxyBase):
    category = 'ndim'
    opens_with = ['.h5', '.hdf5', '.he5', '.gif', '.npz', '.mov', '.mp4']

    def __init__(self):
        pass

    def attach(self, gui):
        gui.ndim = self
        return 'ndim'

    @StaticGuiCall
    def new(title=None):
        """Create a new ndim panel"""
        panel = GuiProxyBase._new('ndim')
        if not title is None:
            panel.long_title = title

        return panel.panid

    @StaticGuiCall
    def open(filepath, new=False):
        """Open a file dialog and open ndim data"""
        if new:
            NdimGuiProxy.new()
            panel = gui.qapp.panels.selected('ndim')
        else:
            panel = gui.qapp.panels.selected('ndim')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('ndim')

        panel.open(filepath)
        return panel.panid

    @StaticGuiCall
    def load_data(data, name=None, dim_names=None, dim_scales=None,  new=False) -> int:
        """Load a np ndarray or xarray DataArray into an ndim panel, open a new panel if needed

        The DataArray can contain additional annotation such as the names of the dimensions,
        and coordinate values (setting the `dim_scales` here). There is no need to use
        dim_names and dim_scales if the data is a xarray DataArray, as this information is
        already present in the DataArray.

        Three special sliders exist:
          * Row: treat a dimension as row index.
          * Col: treat a dimension as column index.
          * Color: treat a dimension as having RGB or RGBA layers.

        All other dimensions become generic sliders.

        :param data: numpy nd array (or xarray DataArray) with the multi dim data.
        :param name: optional name of this data, is used when saving to hdf5.
        :param dim_names: optional list of length ndim with names per dimensions.
        :param dim_scales: optional list with (name, scale) tuples with scale values for each entry in a dim.
        :param new: open a new panel if True, otherwise use the current panel if it exists.
        :return: the panel id of the opened panel.
        """
        if new:
            NdimGuiProxy.new()
            panel = gui.qapp.panels.selected('ndim')
        else:
            panel = gui.qapp.panels.selected('ndim')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('ndim')

        panel.load(data=data, name=name, dim_names=dim_names, dim_scales=dim_scales)
        return panel.panid

    @StaticGuiCall
    def update_data(data):
        """Update the data in the current panel leaving all the rest as is

        This can be used to update the data when the dimensions are the same, but the data has changed.
        """
        panel = gui.qapp.panels.selected('ndim')
        panel.update_data(data)

    @StaticGuiCall
    def get_data() -> 'np.ndarray':
        """Get the data from the current panel"""
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.data

    @StaticGuiCall
    def get_data_name() -> str:
        """Get the name of the data from the current panel"""
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.data_name

    @StaticGuiCall
    def get_dim_names() -> list[str]:
        """Get the names of the dimensions from the current panel"""
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.dim_names

    @StaticGuiCall
    def get_dim_scales() -> list[tuple[str | None, list | None]]:
        """Get the scales of the dimensions from the current panel"""
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.dim_scales

    @StaticGuiCall
    def hide_row_column_color_selection():
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.hide_row_column_color_selection()

    @StaticGuiCall
    def show_row_column_color_selection():
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.show_row_column_color_selection()

    @StaticGuiCall
    def clear_data():
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.clear_data()
