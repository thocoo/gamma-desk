from __future__ import annotations

import logging
from typing import List, Tuple, Union

logger = logging.getLogger(__name__)

from ...core.gui_proxy import GuiProxyBase, StaticGuiCall
from ... import gui


def _resolve_ndim_panel(panid=None):
    if panid is not None:
        return gui.qapp.panels['ndim'][panid]
    return gui.qapp.panels.selected('ndim')


class NdimGuiProxy(GuiProxyBase):
    category = 'ndim'
    opens_with = ['.h5', '.hdf5', '.he5', '.gif', '.npz', '.mov', '.mp4', '.nc', '.nc4']

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
    def select(panid):
        """Make the ndim panel with the given id the active (selected) panel"""
        gui.qapp.panels['ndim'][panid].select()

    @StaticGuiCall
    def open(filepath, panid=None, new=False):
        """Open a file dialog and open ndim data

        :param panid: panel id to use; uses the selected panel when None.
        """
        if panid is not None:
            panel = gui.qapp.panels['ndim'][panid]
        elif new:
            NdimGuiProxy.new()
            panel = gui.qapp.panels.selected('ndim')
        else:
            panel = gui.qapp.panels.selected('ndim')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('ndim')

        panel.open(filepath)
        return panel.panid

    @StaticGuiCall
    def load_data(data, name=None, dim_names=None, dim_scales=None, panid=None, new=False) -> int:
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
        :param panid: panel id to use; uses the selected panel when None. Takes precedence over new.
        :param new: open a new panel if True, otherwise use the current panel if it exists.
        :return: the panel id of the opened panel.
        """
        if panid is not None:
            panel = gui.qapp.panels['ndim'][panid]
        elif new:
            NdimGuiProxy.new()
            panel = gui.qapp.panels.selected('ndim')
        else:
            panel = gui.qapp.panels.selected('ndim')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('ndim')

        panel.load(data=data, name=name, dim_names=dim_names, dim_scales=dim_scales)
        return panel.panid

    @StaticGuiCall
    def update_data(data, panid=None):
        """Update the data in the current panel leaving all the rest as is

        This can be used to update the data when the dimensions are the same, but the data has changed.

        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        panel.update_data(data)

    @StaticGuiCall
    def get_data(panid=None) -> 'np.ndarray':
        """Get the data from the current panel

        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        return panel.main_widget.data

    @StaticGuiCall
    def get_data_name(panid=None) -> str:
        """Get the name of the data from the current panel

        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        return panel.main_widget.data_name

    @StaticGuiCall
    def get_dim_names(panid=None) -> List[str]:
        """Get the names of the dimensions from the current panel

        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        return panel.main_widget.dim_names

    @StaticGuiCall
    def get_dim_scales(panid=None): # -> List[Tuple[str | None, List | None]]
        """Get the scales of the dimensions from the current panel

        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        return panel.main_widget.dim_scales

    @StaticGuiCall
    def hide_row_column_color_selection(panid=None):
        """
        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        return panel.main_widget.hide_row_column_color_selection()

    @StaticGuiCall
    def show_row_column_color_selection(panid=None):
        """
        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        return panel.main_widget.show_row_column_color_selection()

    @StaticGuiCall
    def clear_data(panid=None):
        """
        :param panid: panel id to use; uses the selected panel when None.
        """
        panel = _resolve_ndim_panel(panid)
        return panel.main_widget.clear_data()