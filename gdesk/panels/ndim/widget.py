import numpy as np
from qtpy.QtCore import Qt
from qtpy import QtWidgets


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
        h.addWidget(QtWidgets.QLabel("Row/y-dim: ", self))
        self.rows = QtWidgets.QComboBox(self)
        self.rows.setToolTip("Select which dimension is the row/y dim.")
        h.addWidget(self.rows)
        self.vbox.addLayout(h)
        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel("Column/x-dim: ", self))
        self.cols = QtWidgets.QComboBox(self)
        self.cols.setToolTip("Select which dimension is the col/x dim.")
        h.addWidget(self.cols)
        self.vbox.addLayout(h)
        h = QtWidgets.QHBoxLayout()
        h.addWidget(QtWidgets.QLabel("Color-dim: ", self))
        self.color = QtWidgets.QComboBox(self)
        self.color.setToolTip("Select which dimension is the color dim. Leave None if mono.")
        h.addWidget(self.color)
        self.vbox.addLayout(h)

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

    def update_sliders(self):
        """Update the sliders after the x, y and color dims have changed"""
        self._sliders = dict()
        self._spin_boxes = dict()
        self._dim_combos = dict()
        self._dim_line_edits = dict()
        self._dim_scale_labels = dict()
        self.vbox.removeWidget(self.slider_widget)
        self.slider_widget.deleteLater()
        self.slider_widget = QtWidgets.QWidget(self)
        slider_lay = QtWidgets.QVBoxLayout()

        for dim in range(self.data.ndim):
            if dim in (self.row_dim, self.column_dim, self.color_dim):
                continue
            h = QtWidgets.QHBoxLayout()
            dim_name = QtWidgets.QLineEdit(self.dim_names[dim])
            dim_name.setMaximumWidth(80)
            self._dim_line_edits[dim] = dim_name
            h.addWidget(dim_name)
            scale_name, scale = self.dim_scales[dim]
            if scale is not None:
                if scale_name is not None:
                    scale_name_label = QtWidgets.QLabel(scale_name)
                    h.addWidget(scale_name_label)
                scale_label = QtWidgets.QLabel(f"{scale[0]:.4g}")
                self._dim_scale_labels[dim] = scale_label
                h.addWidget(scale_label)
            h.addSpacerItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum))
            slider_lay.addLayout(h)
            h = QtWidgets.QHBoxLayout()
            slider = QtWidgets.QSlider(Qt.Horizontal, self)
            slider.setMinimum(0)
            slider.setMaximum(self.data.shape[dim]-1)
            slider.setTickInterval(1)
            slider.setSingleStep(1)
            slider.setPageStep(1)
            self._sliders[dim] = slider
            slider.valueChanged.connect(self._update_image)
            h.addWidget(slider)
            spin = QtWidgets.QSpinBox(self)
            spin.setValue(0)
            spin.setMinimum(0)
            spin.setMaximum(self.data.shape[dim]-1)
            spin.setMinimumWidth(40)
            spin.editingFinished.connect(slider.setValue)
            slider.valueChanged.connect(spin.setValue)
            self._spin_boxes[dim] = spin
            h.addWidget(spin)
            lab = QtWidgets.QLabel(f"| {self.data.shape[dim]}")
            lab.setMinimumWidth(20)
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h.addWidget(lab)
            dim_combo = QtWidgets.QComboBox(self)
            dim_combo.addItems(list(self.DIM_CALC.keys()))
            dim_combo.setCurrentIndex(0)
            dim_combo.activated.connect(self._combo_changed)
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

    def _combo_changed(self):
        """Update the sliders behavior based on the combo selection

        The sliders are disabled when 'step' is not selected and the image is refreshed
        """
        for dim, combo in self._dim_combos.items():
            self._sliders[dim].setEnabled(combo.currentText() == 'step')
            self._spin_boxes[dim].setEnabled(combo.currentText() == 'step')

        self._update_image()

    def get_save_data(self):
        """Get all possible relevant data to save to file"""
        # update dim names with possible user adjusts
        for dim, line_edit in self._dim_line_edits.items():
            self.dim_names[dim] = line_edit.text()

        return dict(data=self.data, data_name=self.data_name, dim_names=self.dim_names, dim_scales=self.dim_scales)
