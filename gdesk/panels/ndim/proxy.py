import logging

logger = logging.getLogger(__name__)

from ...core.gui_proxy import GuiProxyBase, StaticGuiCall
from ... import gui


class NdimGuiProxy(GuiProxyBase):
    category = 'ndim'
    # opens_with = ['.tif', '.png', '.gif']

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
    def load_data(data, new=False):
        """Open a new panel if needed and load the data / multidimensional ndarray"""
        if new:
            NdimGuiProxy.new()
            panel = gui.qapp.panels.selected('ndim')
        else:
            panel = gui.qapp.panels.selected('ndim')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('ndim')

        panel.load(data)
        return panel.panid

    @StaticGuiCall
    def update_data(ndarray):
        panel = gui.qapp.panels.selected('ndim')
        panel.update_data(ndarray)

    @StaticGuiCall
    def get_data():
        panel = gui.qapp.panels.selected('ndim')
        return panel.main_widget.data

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
