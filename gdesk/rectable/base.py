import textwrap
import shutil
from collections import OrderedDict

import numpy as np

from .styles import styles

INCR = 100
MAXWIDTH = shutil.get_terminal_size().columns - 4
DEFAULT_STYLE = 'rst-simple'

def lazyf(template):
    frame = sys._getframe(1)
    tesc = template.replace('"','\\"')
    result = eval(f'f"{tesc}"', frame.f_globals, frame.f_locals)
    return result

class ColumnAttributes(object):
    def __init__(self, rectable, colname):
        self._rectable = rectable
        self._colname = colname
        self._attrs = dict()

    def keys(self):
        return tuple(self._attrs.keys())

    def __getitem__(self, key):
        return self._attrs[key]

    def __setitem__(self, key, value):
        self._attrs[key] = value


class ColumnInfo(object):
    def __init__(self, rectable, colname):
        self.rectable = rectable
        self.colname = colname
        self.attrs = ColumnAttributes(self, self.colname)

    def distinct(self):
        return np.unique(self.rectable.sa[self.colname])

    def get_vector(self):
        return self.rectable.sa[self.colname]

    def set_vector(self, value):
        self.rectable.sa[self.colname] = value

    vector = property(get_vector, set_vector)

class More(object):
    def __init__(self, text):
        self.text = text
        self.all_lines = self.text.splitlines()
        self.skip = 0
        self.limit = 20

    @property
    def more(self):
        self.skip += self.limit
        lines = self.all_lines[self.skip:self.skip+self.limit]
        print('\n'.join(lines))

    def __repr__(self):
        lines = self.all_lines[self.skip:self.skip+self.limit]
        return '\n'.join(lines)

class RecordTable(object):
    def __init__(self, fields=[], data=None, size=0, dtype=None):
        """
        fields = ['foo', 'bar', baz']
        or
        fields=[('foo', 'i4'),('bar', 'f4'), ('baz', 'S10')]
        """
        dtype = [(field, 'O') if isinstance(field, str) else field for field in fields] if dtype is None else dtype

        if data is None:
            self._strarr = np.empty(size, dtype=dtype)
        elif isinstance(data, np.ndarray):
            self._strarr = np.array(data, dtype=dtype)
            size = data.size
        else:
            #if data is dataframe
            df = data
            #Remove index??
            self._strarr = df.to_records(index=False)
            size = len(df)

        self._stop = size
        self.base = None
        self.active_row = None
        self.maxcolwidth = None
        self.maxwidth = MAXWIDTH
        self.keepnextlines = True

        self._colinfo = OrderedDict()

        for colname in self._strarr.dtype.names:
            self._colinfo[colname] = ColumnInfo(self, colname)

        self._index_colnames = []

    def set_index(self, colnames):
        if isinstance(colnames, str):
            self._index_colnames = [colnames]
        else:
            assert isinstance(colnames, tuple) or isinstance(colnames, list)
            self._index_colnames = list(colnames)

    def get_column_info(self, colname):
        return self._colinfo[colname]

    @classmethod
    def empty(cls, dtype, size=0):
        self = cls()

    def get_size(self):
        return self._stop

    def set_size(self, length):
        incr = (length - len(self._strarr))
        min_incr = max(incr, INCR)
        self._stop = length
        if self._stop > len(self._strarr):
            self._strarr = np.resize(self._strarr, len(self._strarr) + min_incr)

    size = property(get_size, set_size)

    @property
    def sa(self):
        return self._strarr[0:self._stop]

    @property
    def ra(self):
        return np.rec.array(self.sa, copy=False)

    def copy(self):
        return RecordTable(data=self.sa, dtype=self.sa.dtype)

    @property
    def df(self):
        from pandas import DataFrame
        return DataFrame(self.sa)

    def set_header(self, header, dtypes=None):
        curr_colnames = self.colnames

        if len(header) > len(curr_colnames):
            for colname in header[len(curr_colnames):]:
                self.add_column(colname)

        self.colnames = header

    def __truediv__(self, colname):
        self.add_column(colname)
        return self

    def add_record(self, *record_items, **record_dict):
        if len(record_dict) > 0:
            self.add_record_dict(record_dict)
        else:
            self.add_record_tuple(record_items)

    def add_record_dict(self, record_as_dict):
        record = tuple(record_as_dict[field] for field in self.colnames)
        self.add_record_tuple(record)

    def add_record_tuple(self, record):
        self[self.size] = record

    def add_row(self, row):
        self.add_record_tuple(tuple(row))

    def add_column(self, name, title=None, data=None, dtype=object, method='linear'):
        source = self.sa
        existing_descr = source.dtype.descr
        existing_descr = [] if existing_descr == [('','<f8')] else existing_descr
        self._strarr = np.empty(len(source), dtype=existing_descr+[((title,name), dtype)])
        colnames = source.dtype.names
        if not colnames is None:
            for colname in colnames:
                self._strarr[colname] = source[colname]
        if not data is None:
            m = len(data)
            if method == 'linear':
                if m > self.size:
                    self.size = m
                    self.sa[name] = data
                elif m < self.size:
                    self.sa[name][:m] = data
                else:
                    self.sa[name] = data
            elif method == 'orthogonal':
                prior_n = self.size
                self.size = self.size * m
                self._strarr = np.tile(self.sa, m)
                self.sa[name] = np.repeat(data, prior_n)

    def __getitem__(self, slices):
        if isinstance(slices, RecordTable):
            slices = slices.sa.view(bool)

        elif isinstance(slices, str):
            #result = self.sa.__getitem__(slices)
            result = self.get_column_info(slices)
            return result

        result = self.sa.__getitem__(slices)

        if isinstance(result, np.ndarray):
            arr = RecordTable(dtype=result.dtype)
            arr._strarr = result
            arr._stop = result.size
            return arr

        else:
            return result

    def __setitem__(self, slices, values):
        if isinstance(slices, int) and slices > (self.size-1):
            self.size = slices + 1

        self.sa.__setitem__(slices, values)

    def get_colnames(self):
        if self._strarr.dtype.names is None:
            return []
        return self._strarr.dtype.names

    def set_colnames(self, colnames):
        self._strarr.dtype.names = colnames

    colnames = property(get_colnames, set_colnames)
    field_names = colnames

    def __str__(self):
        return self.tabulate(style=DEFAULT_STYLE)

    def _operate_as_sa(self, func, other):
        if isinstance(other, RecordTable):
            other = other.sa
        result = func(self.sa, other)
        return RecordTable(result, dtype=[('mask', bool)])

    def __or__(self, cell):
        if not self.active_row is None:
            self.active_row.end()
        self.active_row = self.new_record()
        self.active_row.add_cell(cell)
        return self.active_row

    def __eq__(self, other):
        return self._operate_as_sa(np.ndarray.__eq__, other)

    def __ne__(self, other):
        return self._operate_as_sa(np.ndarray.__ne__, other)

    def __lt__(self, other):
        return self._operate_as_sa(np.ndarray.__lt__, other)

    def __le__(self, other):
        return self._operate_as_sa(np.ndarray.__le__, other)

    def __gt__(self, other):
        return self._operate_as_sa(np.ndarray.__gt__, other)

    def __ge__(self, other):
        return self._operate_as_sa(np.ndarray.__ge__, other)

    def __and__(self, other):
        return self._operate_as_sa(np.ndarray.__and__, other)

    def __or__(self, other):
        return self._operate_as_sa(np.ndarray.__or__, other)

    def __xor__(self, other):
        return self._operate_as_sa(np.ndarray.__xor__, other)

    def __len__(self):
        return self.get_size()

    def new_record(self):
        return Record(self)

    def end(self):
        if not self.active_row is None:
            self.active_row.end()
        self.active_row = None

    def tabulate(self, style='rst-simple', haligns='l', valigns='t', maxwidth=None, debug=False, auto_index='pos'):

        if not style in styles.keys():
            raise AttributeError(f"Style {style} doesn't exists. Choose between:\n{styles.keys()}")

        style_param = styles[style]
        art = style_param['art']
        hhaligns = style_param['hhaligns']

        hhaligns = hhaligns.ljust(len(self.colnames), hhaligns[-1])
        haligns = haligns.ljust(len(self.colnames), haligns[-1])
        valigns = valigns.ljust(len(self.colnames), valigns[-1])

        align_map = dict(l = '<', c = '^', r = '>')

        def wrap_paragraph(text):
            lines = []
            for line in text.splitlines():
                lines.extend(txtwr.wrap(line))
            return [''] if len(lines) == 0 else lines

        def wrap_ignore_new_lines(text):
            lines = txtwr.wrap(text)
            return [''] if len(lines) == 0 else lines

        def lines_html(text):
            return [text.replace('\n', '<br>')]

        dtype_obj = [(colname, 'O') for colname in self.colnames]
        if auto_index:
            dtype_obj = [('AUTO_INDEX', 'O')] + dtype_obj
        arr_str = np.empty(self.size, dtype=dtype_obj)

        if auto_index:
            arr_str['AUTO_INDEX'] = [[str(item)] for item in range(self.size)]

        maxwidth = maxwidth or self.maxwidth
        maxcolwidth = maxwidth if self.maxcolwidth is None else self.maxcolwidth

        if auto_index:
            maxcolwidth_index = max(3, max(max(len(line) for line in field) for field in arr_str['AUTO_INDEX']))
            maxcolwidth = min(maxwidth - len(art[3][0]) - len(art[3][3]) - maxcolwidth_index - len(art[3][2]), maxcolwidth)
        else:
            maxcolwidth = min(maxwidth - len(art[3][0]) - len(art[3][3]), maxcolwidth)

        txtwr = textwrap.TextWrapper(maxcolwidth)

        if style == 'html':
            lines_wrapper = lines_html
        else:
            if self.keepnextlines:
                lines_wrapper = wrap_paragraph
            else:
                lines_wrapper = wrap_ignore_new_lines

        for colname in self.colnames:
            arr_str[colname] = [lines_wrapper(str(item)) for item in self.sa[colname]]

        colnames = list(self.colnames)
        titles = list(self.colnames)

        if auto_index:
            colnames = ['AUTO_INDEX'] + colnames
            titles = [auto_index] + titles
            hhaligns = 'r' + hhaligns
            haligns = 'r' + haligns
            valigns = 't' + valigns

        if self.size == 0:
            colwidths = [len(title) for title in titles]
        else:
            colwidths = []
            for colname, title in zip(colnames, titles):
                colwidths.append(max(len(title), max(max(len(line) for line in field) for field in arr_str[colname])))

        result = ''

        def add_line(s):
            nonlocal result
            result += s + '\n'

        def calc_width_for_selection(selection):
            width = len(art[3][0]) + len(art[3][3])
            width += sum(colwidths[pos] + len(art[3][2]) for pos in selection)
            width -= len(art[3][2])
            return width

        selections = []

        if auto_index:
            minumum_selection = [0]
        else:
            minumum_selection = []

        leftover_selection = list(range(len(colnames)))
        [leftover_selection.pop(pos) for pos in minumum_selection]

        start = 0
        stop = 0

        while stop <= len(leftover_selection):
            stop += 1
            scan_selection = minumum_selection.copy()
            scan_selection.extend(leftover_selection[start:stop])
            width = calc_width_for_selection(scan_selection)

            if debug:
                print(f'Start {start}; Stop {stop}; Selection {scan_selection}; Width {width}')

            if (width > maxwidth):
                selections.append(scan_selection[:-1])
                start = stop - 1

            elif stop > len(leftover_selection):
                selections.append(scan_selection)

            if debug:
                print(selections)


        for selection in selections:
            if debug:
                add_line(''.join(str(i % 10) for i in range(maxwidth)))

            selcolwidth = [colwidths[pos] for pos in selection]
            selhaligns = [haligns[pos] for pos in selection]
            selhhaligns = [hhaligns[pos] for pos in selection]
            seltitles = [titles[pos] for pos in selection]

            if not art[0] is None:
                add_line(art[0][0] + art[0][2].join(art[0][1] * colwidth for colwidth in selcolwidth) + art[0][3])

            if not art[1] is None:
                head_template = art[1][0] + art[1][2].join(f"{{{i}:{align_map[align]}{width}}}" for i, (width, align) in enumerate(zip(selcolwidth, selhhaligns))) + art[1][3]
                add_line(head_template.format(*seltitles))

            if not art[2] is None:
                add_line(art[2][0] + art[2][2].join(art[2][1] * colwidth for colwidth in selcolwidth) + art[2][3])

            row_template = art[3][0] + art[3][2].join(f"{{{i}:{align_map[align]}{width}}}" for i, (width, align) in enumerate(zip(selcolwidth, selhaligns))) + art[3][3]

            for ind, record in enumerate(arr_str):
                selrecord = [record[pos] for pos in selection]
                last = ind == (arr_str.size-1)

                line_counts = [len(field) for field in selrecord]
                max_line_count = max(line_counts)

                for linenr in range(max_line_count):
                    line = []
                    for fnr, field in enumerate(selrecord):
                        valign = valigns[fnr]
                        if valign == 't':
                            start = 0
                            stop = len(field)

                        elif valign == 'c':
                            start = (max_line_count - len(field)) // 2
                            stop = start + len(field)

                        elif valign == 'b':
                            start = max_line_count - len(field)
                            stop = max_line_count

                        if start <= linenr < stop:
                            line.append(field[linenr-start])
                        else:
                            line.append('')

                    add_line(row_template.format(*line))

                if not last and not art[4] is None:
                    add_line(art[4][0] + art[4][2].join(art[4][1] * colwidth for colwidth in selcolwidth) + art[4][3])
                elif last and not art[5] is None:
                    add_line(art[5][0] + art[5][2].join(art[5][1] * colwidth for colwidth in selcolwidth) + art[5][3])

        return result

    def get_html_string(self):
        htmlstr = '<table>\n' + self.tabulate(style='html', maxwidth=65536) + '</table>\n'
        return htmlstr

    def to_clipboard_html(self):
        from .htmlclip import PutHtml
        htmlstr = '<table>\n' + self.tabulate(style='html') + '</table>\n'
        PutHtml(htmlstr)

    def to_clipboard_pre_formatted(self):
        import win32clipboard as cb
        try:
            cb.OpenClipboard()
            cb.EmptyClipboard()
            prestr = self.tabulate()
            cb.SetClipboardText(prestr)
        finally:
            cb.CloseClipboard()

    def show(self, ipython=False):
        if ipython:
            ht = self.get_html_string()
            from IPython.core.display import display, HTML
            display(HTML(ht))
        else:
            print(self)


class Record(object):
    def __init__(self, table):
        self.table = table
        self.cells = []

    def add_cell(self, cell):
        self.cells.append(cell)

    def __or__(self, cell):
        self.add_cell(cell)
        return self

    def end(self):
        self.table.add_record(self.cells)



