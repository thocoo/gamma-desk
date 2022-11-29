import pathlib
import numpy as np
from qtpy.QtCore import Qt
from qtpy import QtWidgets, QtGui, QtCore
from ... import config
#
respath = pathlib.Path(config['respath'])


class NdimWidget(QtWidgets.QWidget):
    """Main widget for the ndim panel

    It lets the user select the rows, column and optional color dim
    and lets him slide through the other dims or do some calculations on them.
    """

    DIM_CALC = dict(step=None, mean=np.mean, min=np.min, max=np.max, std=np.std, var=np.var)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.panel = parent

        self.setMinimumHeight(80)
        self.setMinimumWidth(200)

        self.vbox = QtWidgets.QVBoxLayout()
        self.setLayout(self.vbox)

        h = QtWidgets.QHBoxLayout()
        self._row_col_color_labels = list()
        self._row_col_color_labels.append(QtWidgets.QLabel("Row/y-dim: ", self))
        h.addWidget(self._row_col_color_labels[-1])
        self.rows = QtWidgets.QComboBox(self)
        self.rows.setToolTip("Select which dimension is the row/y dim.")
        self.rows.setMinimumHeight(15)
        h.addWidget(self.rows)
        self.vbox.addLayout(h)
        h = QtWidgets.QHBoxLayout()
        self._row_col_color_labels.append(QtWidgets.QLabel("Column/x-dim: ", self))
        h.addWidget(self._row_col_color_labels[-1])
        self.cols = QtWidgets.QComboBox(self)
        self.cols.setMinimumHeight(15)
        self.cols.setToolTip("Select which dimension is the col/x dim.")
        h.addWidget(self.cols)
        self.vbox.addLayout(h)
        h = QtWidgets.QHBoxLayout()
        self._row_col_color_labels.append(QtWidgets.QLabel("Color-dim: ", self))
        h.addWidget(self._row_col_color_labels[-1])
        self.color = QtWidgets.QComboBox(self)
        self.color.setMinimumHeight(15)
        self.color.setToolTip("Select which dimension is the color dim. Leave None if mono.")
        h.addWidget(self.color)
        self.vbox.addLayout(h)
        self._collaps_label = QtWidgets.QLabel("▲")
        self._collaps_label.mousePressEvent = lambda _: self.hide_row_column_color_selection()
        self.vbox.addWidget(self._collaps_label)
        self.vbox.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum,
                                                      QtWidgets.QSizePolicy.Expanding))

        self.rows.activated.connect(self.update_sliders)
        self.cols.activated.connect(self.update_sliders)
        self.color.activated.connect(self.update_sliders)

        self.slider_widget = QtWidgets.QWidget(self)
        self.vbox.addWidget(self.slider_widget)

        self.data = None
        self.data_name = None
        self._color_dim_options = None
        self._sliders = None
        self._spin_boxes = None
        self._dim_combos = None
        self._dim_line_edits = None
        self._dim_scale_labels = None
        self.dim_names = None
        self.dim_scales = None
        self._cycling_dims = list()
        self._play_labels = None
        self.play_icon = QtGui.QPixmap(str(respath / 'icons' / 'px16' / 'control_play.png'))
        self.pause_icon = QtGui.QPixmap(str(respath / 'icons' / 'px16' / 'control_pause.png'))

    def hide_row_column_color_selection(self):
        self.rows.hide()
        self.cols.hide()
        self.color.hide()
        for l in self._row_col_color_labels:
            l.hide()
        self._collaps_label.setText("▼")
        self._collaps_label.mousePressEvent = lambda _: self.show_row_column_color_selection()

    def show_row_column_color_selection(self):
        self.rows.show()
        self.cols.show()
        self.color.show()
        for l in self._row_col_color_labels:
            l.show()
        self._collaps_label.setText("▲")
        self._collaps_label.mousePressEvent = lambda _: self.hide_row_column_color_selection()

    def load(self, data, name=None, dim_names=None, dim_scales=None):
        """Load a new ndim array

        This data can come from code or from the gui that loads a new file
        :param data: numpy nd array with the multi dim data
        :param name: optional name of this data, is used when saving to hdf5
        :param dim_names: optional list of length ndim with names per dimensions
        :param dim_scales: optional list with (name, scale) tuples with scale values for each entry in a dim
        :return: None
        """
        self.data = data
        self.data_name = name
        if self.data is None:
            self.dim_names = None
            self.dim_scales = None
            self.rows.clear()
            self.color.clear()
            self.cols.clear()
            self._color_dim_options = {'None': None}
        else:
            # guess some defaults
            if self.data.ndim > 3 and self.data.shape[-1] in (3, 4):
                def_row = -3
                def_column = -2
                def_color = -1
            else:
                def_row = -2
                def_column = -1
                def_color = None

            if dim_names is None:
                dim_names = [None] * data.ndim
            if dim_scales is None:
                dim_scales = [(None, None)] * data.ndim
            self.dim_names = dim_names
            self.dim_scales = dim_scales
            items = list()
            for i, d in enumerate(self.data.shape):
                if dim_names[i] is None or dim_names[i] == '':
                    dim_names[i] = f"dim-{i}"
                item = f"{dim_names[i]}: [{d}]"
                name, scale = dim_scales[i]
                if name is not None or scale is not None:
                    item += f" - "
                    if name is not None:
                        item += name
                    if scale is not None:
                        item += f" [{scale[0]} - {scale[-1]}]"
                items.append(item)

            self.rows.clear()
            self.rows.addItems(items)
            self.rows.setCurrentIndex(self.data.ndim + def_row)

            self.cols.clear()
            self.cols.addItems(items)
            self.cols.setCurrentIndex(self.data.ndim + def_column)

            self.color.clear()
            self.color.addItem("None")
            self._color_dim_options = {'None': None}
            for i, d in enumerate(self.data.shape):
                if 3 <= d <= 4:
                    text = items[i]
                    self.color.addItem(text)
                    self._color_dim_options[text] = i
            if def_color is None:
                self.color.setCurrentIndex(0)
            else:
                self.color.setCurrentIndex(self.color.count() + def_color)

        self.update_sliders()

    def update_data(self, data):
        """Only update the data but leave the rest as is

        If data is still None or the shape of the current and new data is not the same then the load method is called.
        """
        if self.data is not None and self.data.shape != data.shape:
            self.load(data)
        if self.data is None:
            self.load(data)
        self.data = data
        self._update_image()

    def update_sliders(self):
        """Update the sliders after the x, y and color dims have changed"""
        self._sliders = dict()
        self._spin_boxes = dict()
        self._dim_combos = dict()
        self._dim_line_edits = dict()
        self._dim_scale_labels = dict()
        self._play_labels = dict()
        self._cycling_dims = list()
        self.vbox.removeWidget(self.slider_widget)
        self.slider_widget.deleteLater()
        self.slider_widget = QtWidgets.QWidget(self)
        slider_lay = QtWidgets.QVBoxLayout()

        if self.data is None:
            ndim = 0
        else:
            ndim = self.data.ndim

        for dim in range(ndim):
            if dim in (self.row_dim, self.column_dim, self.color_dim):
                continue
            h = QtWidgets.QHBoxLayout()
            dim_name = QtWidgets.QLineEdit(self.dim_names[dim])
            dim_name.setMaximumWidth(80)
            dim_name.setMinimumHeight(15)
            self._dim_line_edits[dim] = dim_name
            h.addWidget(dim_name)
            scale_name, scale = self.dim_scales[dim]
            if scale is not None:
                if scale_name is not None:
                    scale_name_label = QtWidgets.QLabel(scale_name)
                    scale_name_label.setMinimumHeight(15)
                    h.addWidget(scale_name_label)
                scale_label = QtWidgets.QLabel(f"{scale[0]:.4g}")
                self._dim_scale_labels[dim] = scale_label
                h.addWidget(scale_label)
            h.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
            slider_lay.addLayout(h)
            h = QtWidgets.QHBoxLayout()
            play = QtWidgets.QLabel(self)
            play.setPixmap(self.play_icon)
            play.mousePressEvent = lambda *args, d=dim: self._cycle_dim(dim=d)
            self._play_labels[dim] = play
            play.setMinimumHeight(15)
            h.addWidget(play)
            slider = QtWidgets.QSlider(Qt.Horizontal, self)
            slider.setMinimum(0)
            slider.setMaximum(self.data.shape[dim]-1)
            slider.setTickInterval(1)
            slider.setSingleStep(1)
            slider.setPageStep(1)
            slider.setMinimumHeight(15)
            self._sliders[dim] = slider
            slider.valueChanged.connect(self._update_image)
            h.addWidget(slider)
            spin = QtWidgets.QSpinBox(self)
            spin.setValue(0)
            spin.setMinimum(0)
            spin.setMaximum(self.data.shape[dim]-1)
            spin.setMinimumWidth(40)
            spin.editingFinished.connect(slider.setValue)
            spin.setMinimumHeight(15)
            slider.valueChanged.connect(spin.setValue)
            self._spin_boxes[dim] = spin
            h.addWidget(spin)
            lab = QtWidgets.QLabel(f"| {self.data.shape[dim]}")
            lab.setMinimumWidth(20)
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lab.setMinimumHeight(15)
            h.addWidget(lab)
            dim_combo = QtWidgets.QComboBox(self)
            dim_combo.addItems(list(self.DIM_CALC.keys()))
            dim_combo.setCurrentIndex(0)
            dim_combo.setMinimumHeight(15)
            dim_combo.activated.connect(lambda *args, d=dim: self._combo_changed(d))
            self._dim_combos[dim] = dim_combo
            h.addWidget(dim_combo)
            slider_lay.addLayout(h)
            slider_lay.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding))
        self.slider_widget.setLayout(slider_lay)
        self.slider_widget.setMinimumHeight(10 + 25 * len(self._sliders))
        self.vbox.addWidget(self.slider_widget)
        self._update_image()

    @property
    def row_dim(self):
        return self.rows.currentIndex()

    @property
    def column_dim(self):
        return self.cols.currentIndex()

    @property
    def color_dim(self):
        return self._color_dim_options[self.color.currentText()]

    def _update_image(self):
        """Update output image after sliders or calc options have changed"""
        if self.data is None:
            return
        # get the indexes right
        indexes = [0] * self.data.ndim
        indexes[self.row_dim] = slice(None)
        indexes[self.column_dim] = slice(None)
        if self.color_dim is not None:
            indexes[self.color_dim] = slice(None)
        for dim, slider in self._sliders.items():
            if self._dim_combos[dim].currentText() == 'step':
                indexes[dim] = slice(slider.value(), slider.value()+1)  # use slicing to not (yet) loose the dim
            else:
                indexes[dim] = slice(None)  # for calculations, we need all the data

        # do the actual indexing
        im = self.data[tuple(indexes)]

        # perform any calculations if needed
        for dim, combo in reversed(self._dim_combos.items()):
            combo_text = combo.currentText()
            if combo_text == 'step':
                pass
            else:
                im = self.DIM_CALC[combo_text](im, axis=dim)

        # get rid of any dims with len 1
        im = im.squeeze()

        # move around the axis until we have row/col and optionally color in this particular order
        if self.color_dim is None:
            if self.row_dim > self.column_dim:
                im = np.moveaxis(im, 0, 1)
        else:
            if not self.row_dim < self.column_dim < self.color_dim:
                im = np.moveaxis(im, np.argsort(np.array((self.row_dim, self.column_dim, self.color_dim))),
                                 (0, 1, 2))

        # send to any image viewer panel that is connected
        for panel in self.parent().targetPanels('image'):
            panel.show_array(im, zoomFitHist=False, log=False)

        # update the scales
        for dim, scale_label in self._dim_scale_labels.items():
            scale_label.setText(f"{self.dim_scales[dim][1][self._sliders[dim].value()]:.4g}")

    def _combo_changed(self, dim):
        """Update the sliders behavior based on the combo selection

        The sliders are disabled when 'step' is not selected and the image is refreshed
        """
        if self._dim_combos[dim].currentText() == 'step':
            self._sliders[dim].setEnabled(True)
            self._spin_boxes[dim].setEnabled(True)
        else:
            self._sliders[dim].setEnabled(False)
            self._spin_boxes[dim].setEnabled(False)
            if dim in self._cycling_dims:
                self._cycle_dim(dim=dim)
        self._update_image()

    def get_save_data(self):
        """Get all possible relevant data to save to file"""
        # update dim names with possible user adjusts
        for dim, line_edit in self._dim_line_edits.items():
            self.dim_names[dim] = line_edit.text()

        return dict(data=self.data, data_name=self.data_name, dim_names=self.dim_names, dim_scales=self.dim_scales)

    def _cycle_dim(self, dim):
        """handle the automatic cycling of a dim (play/pause button)"""
        if dim in self._cycling_dims:
            self._cycling_dims.remove(dim)
            self._play_labels[dim].setPixmap(self.play_icon)
        else:
            if self._dim_combos[dim].currentText() != 'step':
                return
            self._play_labels[dim].setPixmap(self.pause_icon)
            self._cycling_dims.append(dim)
        if len(self._cycling_dims):
            self._cycle_timer = QtCore.QTimer()
            self._cycle_timer.timeout.connect(lambda: self._advance_dim(0))
            self._cycle_timer.start(250)
        else:
            self._cycle_timer.stop()

    def _advance_dim(self, ind):
        """Recursive method to advance in the automatic cycling

        If one cycle overflows then it advances the second one in the list.
        The order in which the dims are added to the _cycling_dims is used for this.
        """
        try:
            dim = self._cycling_dims[ind]
        except IndexError:
            return
        val = self._spin_boxes[dim].value()
        if val == self._spin_boxes[dim].maximum():
            self._advance_dim(ind+1)
            self._spin_boxes[dim].setValue(0)
            self._sliders[dim].setValue(0)
        else:
            self._spin_boxes[dim].setValue(val+1)
            self._sliders[dim].setValue(val+1)

    def clear_data(self):
        """Clear current data and put back in startup state"""
        self.data = None
        self.load(data=None)
