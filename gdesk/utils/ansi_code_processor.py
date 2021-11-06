""" Utilities for processing ANSI escape codes and special ASCII characters.
"""
#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import sys

# Standard library imports
from collections import namedtuple
import re

# System library imports
from qtpy import QtGui

#-----------------------------------------------------------------------------
# Constants and datatypes
#-----------------------------------------------------------------------------

# An action for erase requests (ED and EL commands).
EraseAction = namedtuple('EraseAction', ['action', 'area', 'erase_to'])

# An action for cursor move requests (CUU, CUD, CUF, CUB, CNL, CPL, CHA, CUP,
# and HVP commands).
# FIXME: Not implemented in AnsiCodeProcessor.
MoveAction = namedtuple('MoveAction', ['action', 'dir', 'unit', 'count'])

# An action for scroll requests (SU and ST) and form feeds.
ScrollAction = namedtuple('ScrollAction', ['action', 'dir', 'unit', 'count'])

# An action for the carriage return character
CarriageReturnAction = namedtuple('CarriageReturnAction', ['action'])

# An action for the \n character
NewLineAction = namedtuple('NewLineAction', ['action'])

# An action for the beep character
BeepAction = namedtuple('BeepAction', ['action'])

# An action for backspace
BackSpaceAction = namedtuple('BackSpaceAction', ['action'])

# An action for backspace
SetTitleAction = namedtuple('SetTitleAction', ['action', 'title'])

# Regular expressions.
CSI_COMMANDS = 'ABCDEFGHJKSTfmnsu'
CSI_DOS = 'X'
CSI_SUBPATTERN = '\[(.*?)([%s])' % (CSI_COMMANDS + CSI_DOS)
OSC_SUBPATTERN = '\](.*?)[\x07\x1b]'
ANSI_PATTERN = ('\x01?\x1b(%s|%s)\x02?' % \
                (CSI_SUBPATTERN, OSC_SUBPATTERN))
ANSI_OR_SPECIAL_PATTERN = re.compile('(\a|\b|\r(?!\n)|\r?\n)|(?:%s)' % ANSI_PATTERN)
SPECIAL_PATTERN = re.compile('([\f])')

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------


class AnsiCodeProcessor:
    
    """
    Translates special ASCII characters and ANSI escape codes into readable
    attributes. It also supports a few non-standard, xterm-specific codes.
    """

    # Whether to increase intensity or set boldness for SGR code 1.
    # (Different terminals handle this in different ways.)
    bold_text_enabled = False

    # We provide an empty default color map because subclasses will likely want
    # to use a custom color format.
    default_color_map = {}

    #---------------------------------------------------------------------------
    # AnsiCodeProcessor interface
    #---------------------------------------------------------------------------

    def __init__(self):
        self.actions = []
        self.color_map = self.default_color_map.copy()
        self.reset_sgr()

    def reset_sgr(self):
        """ Reset graphics attributs to their default values.
        """
        self.intensity = 0
        self.italic = False
        self.bold = False
        self.underline = False
        self.foreground_color = None
        self.background_color = None

    def split_string(self, string):
        """ Yields substrings for which the same escape code applies.
        """
        self.actions = []
        start = 0

        # strings ending with \r are assumed to be ending in \r\n since
        # \n is appended to output strings automatically.  Accounting
        # for that, here.
        last_char = '\n' if len(string) > 0 and string[-1] == '\n' else None
        string = string[:-1] if last_char is not None else string
        

        for match in ANSI_OR_SPECIAL_PATTERN.finditer(string):
            raw = string[start:match.start()]
            substring = SPECIAL_PATTERN.sub(self._replace_special, raw)
            if substring or self.actions:
                yield substring
                self.actions = []
            start = match.end()

            groups = [x for x in match.groups() if x is not None]
            g0 = groups[0]
            if g0 == '\a':
                self.actions.append(BeepAction('beep'))
                yield None
                self.actions = []
            elif g0 == '\r':
                self.actions.append(CarriageReturnAction('carriage-return'))
                yield None
                self.actions = []
            elif g0 == '\b':
                self.actions.append(BackSpaceAction('backspace'))
                yield None
                self.actions = []
            elif g0 == '\n' or g0 == '\r\n':
                self.actions.append(NewLineAction('newline'))
                yield g0
                self.actions = []
            else:
                params = [ param for param in groups[1].split(';') if param ]
                if g0.startswith('['):
                    # Case 1: CSI code.
                    try:
                        params = list(map(int, params))
                    except ValueError:
                        # Silently discard badly formed codes.
                        pass
                    else:
                        self.set_csi_code(groups[2], params)

                elif g0.startswith(']'):
                    # Case 2: OSC code.
                    self.set_osc_code(params)

        raw = string[start:]
        substring = SPECIAL_PATTERN.sub(self._replace_special, raw)
        if substring or self.actions:
            yield substring

        if last_char is not None:
            self.actions.append(NewLineAction('newline'))
            yield last_char

    def set_csi_code(self, command, params=[]):
        """ Set attributes based on CSI (Control Sequence Introducer) code.

        Parameters
        ----------
        command : str
            The code identifier, i.e. the final character in the sequence.

        params : sequence of integers, optional
            The parameter codes for the command.
        """
        if command == 'm':   # SGR - Select Graphic Rendition
            if params:
                self.set_sgr_code(params)
            else:
                self.set_sgr_code([0])

        elif (command == 'J' or # ED - Erase Data
              command == 'K'):  # EL - Erase in Line
            code = params[0] if params else 0
            if 0 <= code <= 2:
                area = 'screen' if command == 'J' else 'line'
                if code == 0:
                    erase_to = 'end'
                elif code == 1:
                    erase_to = 'start'
                elif code == 2:
                    erase_to = 'all'
                self.actions.append(EraseAction('erase', area, erase_to))

        elif (command == 'S' or # SU - Scroll Up
              command == 'T'):  # SD - Scroll Down
            dir = 'up' if command == 'S' else 'down'
            count = params[0] if params else 1
            self.actions.append(ScrollAction('scroll', dir, 'line', count))
            
        elif command == 'X':  #from the Windows pty
            #https://docs.microsoft.com/en-us/windows/console/console-virtual-terminal-sequences#text-modification
            #Erase <n> characters from the current cursor position by overwriting them with a space character.
            print(f'CSI cmd: {command}, params: {params}')

    def set_osc_code(self, params):
        """ Set attributes based on OSC (Operating System Command) parameters.

        Parameters
        ----------
        params : sequence of str
            The parameters for the command.
        """
        try:
            command = int(params.pop(0))
        except (IndexError, ValueError):
            return
            
        if command == 0:
            print(f'OS cmd: {command}, params: {params}')            
            self.actions.append(SetTitleAction('set-title', params[0]))

        elif command == 4:
            # xterm-specific: set color number to color spec.
            try:
                color = int(params.pop(0))
                spec = params.pop(0)
                self.color_map[color] = self._parse_xterm_color_spec(spec)
            except (IndexError, ValueError):
                pass

    def set_sgr_code(self, params):
        """ Set attributes based on SGR (Select Graphic Rendition) codes.

        Parameters
        ----------
        params : sequence of ints
            A list of SGR codes for one or more SGR commands. Usually this
            sequence will have one element per command, although certain
            xterm-specific commands requires multiple elements.
        """
        # Always consume the first parameter.
        if not params:
            return
        code = params.pop(0)

        if code == 0:
            self.reset_sgr()
        elif code == 1:
            if self.bold_text_enabled:
                self.bold = True
            else:
                self.intensity = 1
        elif code == 2:
            self.intensity = 0
        elif code == 3:
            self.italic = True
        elif code == 4:
            self.underline = True
        elif code == 22:
            self.intensity = 0
            self.bold = False
        elif code == 23:
            self.italic = False
        elif code == 24:
            self.underline = False
        elif code >= 30 and code <= 37:
            self.foreground_color = code - 30
        elif code == 38 and params and params.pop(0) == 5:
            # xterm-specific: 256 color support.
            if params:
                self.foreground_color = params.pop(0)
        elif code == 39:
            self.foreground_color = None
        elif code >= 40 and code <= 47:
            self.background_color = code - 40
        elif code == 48 and params and params.pop(0) == 5:
            # xterm-specific: 256 color support.
            if params:
                self.background_color = params.pop(0)
        elif code == 49:
            self.background_color = None

        # Recurse with unconsumed parameters.
        self.set_sgr_code(params)

    #---------------------------------------------------------------------------
    # Protected interface
    #---------------------------------------------------------------------------

    def _parse_xterm_color_spec(self, spec):
        if spec.startswith('rgb:'):
            return tuple([int(x, 16) for x in spec[4:].split('/')])
        elif spec.startswith('rgbi:'):
            return tuple([int(float(x) * 255) for x in spec[5:].split('/')])
        elif spec == '?':
            raise ValueError('Unsupported xterm color spec')
        return spec

    def _replace_special(self, match):
        special = match.group(1)
        if special == '\f':
            self.actions.append(ScrollAction('scroll', 'down', 'page', 1))
        return ''


class QtAnsiCodeProcessor(AnsiCodeProcessor):
    
    """
    Translates ANSI escape codes into QTextCharFormats.
    """
   
    color_plot_demo = '''for i in range(32):
    s = ''
    for j in range(8):
        n = j + i * 8
        s += "\033[1m %3d: \033[0m \033[48;5;%dm     \033[0m   " % (n,n)
    print(s)'''   
    
    xterm256_colors = {
          0 : (0x00, 0x00, 0x00),
          1 : (0x80, 0x00, 0x00),
          2 : (0x00, 0x80, 0x00),
          3 : (0x80, 0x80, 0x00),
          4 : (0x00, 0x00, 0x80),
          5 : (0x80, 0x00, 0x80),
          6 : (0x00, 0x80, 0x80),
          7 : (0xc0, 0xc0, 0xc0),
          8 : (0x80, 0x80, 0x80),
          9 : (0xff, 0x00, 0x00),
         10 : (0x00, 0xff, 0x00),
         11 : (0xff, 0xff, 0x00),
         12 : (0x00, 0x00, 0xff),
         13 : (0xff, 0x00, 0xff),
         14 : (0x00, 0xff, 0xff),
         15 : (0xff, 0xff, 0xff),        
         16 : (0x00, 0x00, 0x00),
         17 : (0x00, 0x00, 0x5f),
         18 : (0x00, 0x00, 0x87),
         19 : (0x00, 0x00, 0xaf),
         20 : (0x00, 0x00, 0xd7),
         21 : (0x00, 0x00, 0xff),
         22 : (0x00, 0x5f, 0x00),
         23 : (0x00, 0x5f, 0x5f),
         24 : (0x00, 0x5f, 0x87),
         25 : (0x00, 0x5f, 0xaf),
         26 : (0x00, 0x5f, 0xd7),
         27 : (0x00, 0x5f, 0xff),
         28 : (0x00, 0x87, 0x00),
         29 : (0x00, 0x87, 0x5f),
         30 : (0x00, 0x87, 0x87),
         31 : (0x00, 0x87, 0xaf),
         32 : (0x00, 0x87, 0xd7),
         33 : (0x00, 0x87, 0xff),
         34 : (0x00, 0xaf, 0x00),
         35 : (0x00, 0xaf, 0x5f),
         36 : (0x00, 0xaf, 0x87),
         37 : (0x00, 0xaf, 0xaf),
         38 : (0x00, 0xaf, 0xd7),
         39 : (0x00, 0xaf, 0xff),
         40 : (0x00, 0xd7, 0x00),
         41 : (0x00, 0xd7, 0x5f),
         42 : (0x00, 0xd7, 0x87),
         43 : (0x00, 0xd7, 0xaf),
         44 : (0x00, 0xd7, 0xd7),
         45 : (0x00, 0xd7, 0xff),
         46 : (0x00, 0xff, 0x00),
         47 : (0x00, 0xff, 0x5f),
         48 : (0x00, 0xff, 0x87),
         49 : (0x00, 0xff, 0xaf),
         50 : (0x00, 0xff, 0xd7),
         51 : (0x00, 0xff, 0xff),
         52 : (0x5f, 0x00, 0x00),
         53 : (0x5f, 0x00, 0x5f),
         54 : (0x5f, 0x00, 0x87),
         55 : (0x5f, 0x00, 0xaf),
         56 : (0x5f, 0x00, 0xd7),
         57 : (0x5f, 0x00, 0xff),
         58 : (0x5f, 0x5f, 0x00),
         59 : (0x5f, 0x5f, 0x5f),
         60 : (0x5f, 0x5f, 0x87),
         61 : (0x5f, 0x5f, 0xaf),
         62 : (0x5f, 0x5f, 0xd7),
         63 : (0x5f, 0x5f, 0xff),
         64 : (0x5f, 0x87, 0x00),
         65 : (0x5f, 0x87, 0x5f),
         66 : (0x5f, 0x87, 0x87),
         67 : (0x5f, 0x87, 0xaf),
         68 : (0x5f, 0x87, 0xd7),
         69 : (0x5f, 0x87, 0xff),
         70 : (0x5f, 0xaf, 0x00),
         71 : (0x5f, 0xaf, 0x5f),
         72 : (0x5f, 0xaf, 0x87),
         73 : (0x5f, 0xaf, 0xaf),
         74 : (0x5f, 0xaf, 0xd7),
         75 : (0x5f, 0xaf, 0xff),
         76 : (0x5f, 0xd7, 0x00),
         77 : (0x5f, 0xd7, 0x5f),
         78 : (0x5f, 0xd7, 0x87),
         79 : (0x5f, 0xd7, 0xaf),
         80 : (0x5f, 0xd7, 0xd7),
         81 : (0x5f, 0xd7, 0xff),
         82 : (0x5f, 0xff, 0x00),
         83 : (0x5f, 0xff, 0x5f),
         84 : (0x5f, 0xff, 0x87),
         85 : (0x5f, 0xff, 0xaf),
         86 : (0x5f, 0xff, 0xd7),
         87 : (0x5f, 0xff, 0xff),
         88 : (0x87, 0x00, 0x00),
         89 : (0x87, 0x00, 0x5f),
         90 : (0x87, 0x00, 0x87),
         91 : (0x87, 0x00, 0xaf),
         92 : (0x87, 0x00, 0xd7),
         93 : (0x87, 0x00, 0xff),
         94 : (0x87, 0x5f, 0x00),
         95 : (0x87, 0x5f, 0x5f),
         96 : (0x87, 0x5f, 0x87),
         97 : (0x87, 0x5f, 0xaf),
         98 : (0x87, 0x5f, 0xd7),
         99 : (0x87, 0x5f, 0xff),
        100 : (0x87, 0x87, 0x00),
        101 : (0x87, 0x87, 0x5f),
        102 : (0x87, 0x87, 0x87),
        103 : (0x87, 0x87, 0xaf),
        104 : (0x87, 0x87, 0xd7),
        105 : (0x87, 0x87, 0xff),
        106 : (0x87, 0xaf, 0x00),
        107 : (0x87, 0xaf, 0x5f),
        108 : (0x87, 0xaf, 0x87),
        109 : (0x87, 0xaf, 0xaf),
        110 : (0x87, 0xaf, 0xd7),
        111 : (0x87, 0xaf, 0xff),
        112 : (0x87, 0xd7, 0x00),
        113 : (0x87, 0xd7, 0x5f),
        114 : (0x87, 0xd7, 0x87),
        115 : (0x87, 0xd7, 0xaf),
        116 : (0x87, 0xd7, 0xd7),
        117 : (0x87, 0xd7, 0xff),
        118 : (0x87, 0xff, 0x00),
        119 : (0x87, 0xff, 0x5f),
        120 : (0x87, 0xff, 0x87),
        121 : (0x87, 0xff, 0xaf),
        122 : (0x87, 0xff, 0xd7),
        123 : (0x87, 0xff, 0xff),
        124 : (0xaf, 0x00, 0x00),
        125 : (0xaf, 0x00, 0x5f),
        126 : (0xaf, 0x00, 0x87),
        127 : (0xaf, 0x00, 0xaf),
        128 : (0xaf, 0x00, 0xd7),
        129 : (0xaf, 0x00, 0xff),
        130 : (0xaf, 0x5f, 0x00),
        131 : (0xaf, 0x5f, 0x5f),
        132 : (0xaf, 0x5f, 0x87),
        133 : (0xaf, 0x5f, 0xaf),
        134 : (0xaf, 0x5f, 0xd7),
        135 : (0xaf, 0x5f, 0xff),
        136 : (0xaf, 0x87, 0x00),
        137 : (0xaf, 0x87, 0x5f),
        138 : (0xaf, 0x87, 0x87),
        139 : (0xaf, 0x87, 0xaf),
        140 : (0xaf, 0x87, 0xd7),
        141 : (0xaf, 0x87, 0xff),
        142 : (0xaf, 0xaf, 0x00),
        143 : (0xaf, 0xaf, 0x5f),
        144 : (0xaf, 0xaf, 0x87),
        145 : (0xaf, 0xaf, 0xaf),
        146 : (0xaf, 0xaf, 0xd7),
        147 : (0xaf, 0xaf, 0xff),
        148 : (0xaf, 0xd7, 0x00),
        149 : (0xaf, 0xd7, 0x5f),
        150 : (0xaf, 0xd7, 0x87),
        151 : (0xaf, 0xd7, 0xaf),
        152 : (0xaf, 0xd7, 0xd7),
        153 : (0xaf, 0xd7, 0xff),
        154 : (0xaf, 0xff, 0x00),
        155 : (0xaf, 0xff, 0x5f),
        156 : (0xaf, 0xff, 0x87),
        157 : (0xaf, 0xff, 0xaf),
        158 : (0xaf, 0xff, 0xd7),
        159 : (0xaf, 0xff, 0xff),
        160 : (0xd7, 0x00, 0x00),
        161 : (0xd7, 0x00, 0x5f),
        162 : (0xd7, 0x00, 0x87),
        163 : (0xd7, 0x00, 0xaf),
        164 : (0xd7, 0x00, 0xd7),
        165 : (0xd7, 0x00, 0xff),
        166 : (0xd7, 0x5f, 0x00),
        167 : (0xd7, 0x5f, 0x5f),
        168 : (0xd7, 0x5f, 0x87),
        169 : (0xd7, 0x5f, 0xaf),
        170 : (0xd7, 0x5f, 0xd7),
        171 : (0xd7, 0x5f, 0xff),
        172 : (0xd7, 0x87, 0x00),
        173 : (0xd7, 0x87, 0x5f),
        174 : (0xd7, 0x87, 0x87),
        175 : (0xd7, 0x87, 0xaf),
        176 : (0xd7, 0x87, 0xd7),
        177 : (0xd7, 0x87, 0xff),
        178 : (0xd7, 0xaf, 0x00),
        179 : (0xd7, 0xaf, 0x5f),
        180 : (0xd7, 0xaf, 0x87),
        181 : (0xd7, 0xaf, 0xaf),
        182 : (0xd7, 0xaf, 0xd7),
        183 : (0xd7, 0xaf, 0xff),
        184 : (0xd7, 0xd7, 0x00),
        185 : (0xd7, 0xd7, 0x5f),
        186 : (0xd7, 0xd7, 0x87),
        187 : (0xd7, 0xd7, 0xaf),
        188 : (0xd7, 0xd7, 0xd7),
        189 : (0xd7, 0xd7, 0xff),
        190 : (0xd7, 0xff, 0x00),
        191 : (0xd7, 0xff, 0x5f),
        192 : (0xd7, 0xff, 0x87),
        193 : (0xd7, 0xff, 0xaf),
        194 : (0xd7, 0xff, 0xd7),
        195 : (0xd7, 0xff, 0xff),
        196 : (0xff, 0x00, 0x00),
        197 : (0xff, 0x00, 0x5f),
        198 : (0xff, 0x00, 0x87),
        199 : (0xff, 0x00, 0xaf),
        200 : (0xff, 0x00, 0xd7),
        201 : (0xff, 0x00, 0xff),
        202 : (0xff, 0x5f, 0x00),
        203 : (0xff, 0x5f, 0x5f),
        204 : (0xff, 0x5f, 0x87),
        205 : (0xff, 0x5f, 0xaf),
        206 : (0xff, 0x5f, 0xd7),
        207 : (0xff, 0x5f, 0xff),
        208 : (0xff, 0x87, 0x00),
        209 : (0xff, 0x87, 0x5f),
        210 : (0xff, 0x87, 0x87),
        211 : (0xff, 0x87, 0xaf),
        212 : (0xff, 0x87, 0xd7),
        213 : (0xff, 0x87, 0xff),
        214 : (0xff, 0xaf, 0x00),
        215 : (0xff, 0xaf, 0x5f),
        216 : (0xff, 0xaf, 0x87),
        217 : (0xff, 0xaf, 0xaf),
        218 : (0xff, 0xaf, 0xd7),
        219 : (0xff, 0xaf, 0xff),
        220 : (0xff, 0xd7, 0x00),
        221 : (0xff, 0xd7, 0x5f),
        222 : (0xff, 0xd7, 0x87),
        223 : (0xff, 0xd7, 0xaf),
        224 : (0xff, 0xd7, 0xd7),
        225 : (0xff, 0xd7, 0xff),
        226 : (0xff, 0xff, 0x00),
        227 : (0xff, 0xff, 0x5f),
        228 : (0xff, 0xff, 0x87),
        229 : (0xff, 0xff, 0xaf),
        230 : (0xff, 0xff, 0xd7),
        231 : (0xff, 0xff, 0xff),
        232 : (0x08, 0x08, 0x08),
        233 : (0x12, 0x12, 0x12),
        234 : (0x1c, 0x1c, 0x1c),
        235 : (0x26, 0x26, 0x26),
        236 : (0x30, 0x30, 0x30),
        237 : (0x3a, 0x3a, 0x3a),
        238 : (0x44, 0x44, 0x44),
        239 : (0x4e, 0x4e, 0x4e),
        240 : (0x58, 0x58, 0x58),
        241 : (0x60, 0x60, 0x60),
        242 : (0x66, 0x66, 0x66),
        243 : (0x76, 0x76, 0x76),
        244 : (0x80, 0x80, 0x80),
        245 : (0x8a, 0x8a, 0x8a),
        246 : (0x94, 0x94, 0x94),
        247 : (0x9e, 0x9e, 0x9e),
        248 : (0xa8, 0xa8, 0xa8),
        249 : (0xb2, 0xb2, 0xb2),
        250 : (0xbc, 0xbc, 0xbc),
        251 : (0xc6, 0xc6, 0xc6),
        252 : (0xd0, 0xd0, 0xd0),
        253 : (0xda, 0xda, 0xda),
        254 : (0xe4, 0xe4, 0xe4),
        255 : (0xee, 0xee, 0xee)}

    # Set the default color map for super class.
    default_color_map = xterm256_colors.copy()
    bold_text_enabled = True

    def get_color(self, color, intensity=0):
        """ Returns a QColor for a given color code, or None if one cannot be
            constructed.
        """
        if color is None:
            return None

        # Adjust for intensity, if possible.
        if color < 8 and intensity > 0:
            color += 8

        constructor = self.color_map.get(color, None)
        if isinstance(constructor, str):
            # If this is an X11 color name, we just hope there is a close SVG
            # color name. We could use QColor's static method
            # 'setAllowX11ColorNames()', but this is global and only available
            # on X11. It seems cleaner to aim for uniformity of behavior.
            return QtGui.QColor(constructor)

        elif isinstance(constructor, (tuple, list)):
            return QtGui.QColor(*constructor)

        return None

    def get_format(self):
        """ Returns a QTextCharFormat that encodes the current style attributes.
        """
        format = QtGui.QTextCharFormat()

        # Set foreground color
        qcolor = self.get_color(self.foreground_color, self.intensity)
        if qcolor is not None:
            format.setForeground(qcolor)

        # Set background color
        qcolor = self.get_color(self.background_color, self.intensity)
        if qcolor is not None:
            format.setBackground(qcolor)

        # Set font weight/style options
        if self.bold:
            format.setFontWeight(QtGui.QFont.Bold)
        else:
            format.setFontWeight(QtGui.QFont.Normal)
        format.setFontItalic(self.italic)
        format.setFontUnderline(self.underline)

        return format

    def set_background_color(self, color):
        """ Given a background color (a QColor), attempt to set a color map
            that will be aesthetically pleasing.
        """
        # Set a new default color map.
        self.default_color_map = self.darkbg_color_map.copy()

        if color.value() >= 127:
            # Colors appropriate for a terminal with a light background. For
            # now, only use non-bright colors...
            for i in range(8):
                self.default_color_map[i + 8] = self.default_color_map[i]

            # ...and replace white with black.
            self.default_color_map[7] = self.default_color_map[15] = 'black'

        # Update the current color map with the new defaults.
        self.color_map.update(self.default_color_map)
