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
        panel = GuiProxyBase._new('ndim')
        if not title is None:
            panel.long_title = title

        return panel.panid

    @StaticGuiCall
    def open(filepath, new=False):
        if new:
            NdimGuiProxy.new()
            panel = gui.qapp.panels.selected('ndim')
        else:
            panel = gui.qapp.panels.selected('ndim')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('ndim')
        panel.open(filepath)
        window = panel.get_container().parent()
        window.raise_()
        gui.qapp.processEvents()
        return panel.panid

    @StaticGuiCall
    def open_array(array, new=False):
        if new:
            NdimGuiProxy.new()
            panel = gui.qapp.panels.selected('ndim')
        else:
            panel = gui.qapp.panels.selected('ndim')
            if panel is None:
                panel = gui.qapp.panels.select_or_new('ndim')

        panel.load(array)

        window = panel.get_container().parent()
        window.raise_()
        gui.qapp.processEvents()
        return panel.panid

    @StaticGuiCall
    def set_data(ndarray):
        panel = gui.qapp.panels.selected('ndim')
        panel.load(ndarray)

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