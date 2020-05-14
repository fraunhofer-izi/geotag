#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2019 Gesellschaft zur Foerderung der angewandten Forschung e.V.
# acting on behalf of its Fraunhofer Institute for Cell Therapy and Immunology
# (IZI).
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License along with
# this program. If not, see http://www.gnu.org/licenses/.

import os
import curses
from curses.textpad import Textbox, rectangle
import locale
import logging
from pydoc import locate
from datetime import datetime
import glob
import random
import yaml
import pandas as pd
import numpy as np
from .undo import stack, undoable

# use system default localization
locale.setlocale(locale.LC_ALL, 'C')
CODE = locale.getpreferredencoding()


TCOLORS = [196, 203, 202, 208, 178, 148, 106, 71, 31, 26]
TAG_CHARS = ['editor', 'key', 'type', 'col_width', 'desc']
default_tags = {
    'quality': {
        'type': 'int',
        'desc': 'From 0 (bad) to 9 (perfect).\n'
        '0 - unrelated or no data\n'
        '1 - bad annotation\n'
        '2 - bad sample\n'
        '3\n'
        '4\n'
        '5\n'
        '6\n'
        '7\n'
        '8\n'
        '9 - perfect sample',
        'editor': 'maintainer',
        'key': 'q',
        'col_width': 8
    },
    'note': {
        'type': 'str',
        'desc': 'A note.',
        'editor': 'maintainer',
        'key': 'n',
        'col_width': 20
    }
}


def uniquify(vals):
    seen = set()
    for item in vals:
        fudge = 1
        newitem = item
        while newitem in seen:
            fudge += 1
            newitem = "{}_{}".format(item, fudge)
        yield newitem
        seen.add(newitem)


class App:

    __version__ = '0.2.0'
    missing_data_value = '-'
    tag_description_max_hight = 15
    _byte_numbers = {str(i).encode() for i in range(10)}
    _control_seq_parts = _byte_numbers.copy()
    _control_seq_parts.add(b';')
    _control_seq_parts.add(b'[')
    _required_columns = {'id', 'gse'}
    view_attributes = {
        'selection',
        'pointer',
        'col_pointer',
        'tag_pointer',
        'top',
        'df',
        'header',
        'filter',
        'show_columns',
        'sort_columns',
        'sort_reverse_columns',
        'ordered_columns',
        'color_by'
    }
    _window_width = 140
    _helptext = """
        h               Show/hide help window.
        v               View-dialog.
        t               Tag-dialog.
        s               Manual synchronous save. (auto-saves after each action)
        l               Reload data table.
        q               Quit geotag.

        0-9             Set tag info for selected samples.
        d               Delete tag info for selected samples.
        u               Undo.
        r               Redo.

        Enter           Show sample in gse-soft-file.
        o               Organize tmux panes.

        Up              Move upward.
        Down            Move downward.
        Shift+Up        Select upward.
        Shift+Down      Select downward.
        Ctrl+Up         Jump to next untagged entry above.
        Ctrl+Donw       Jump to next untagged entry below.
        Ctrl+Shift+Up   Add next untagged entry above to selection.
        Ctrl+Shift+Down Add next untagged entry below to selection.
        Pageup          Move upward one page.
        Pagedown        Move down one page.
        Shift+Pageup    Select upward one page.
        ShiftPagedown   Select down one page.
        Home            Move to the start of the table.
        End             Move to the end of the table.
        g               Go to position dialog.
        G               Go to and add position to selection dialog.
        f               Search for string in displayed columns.
        F               Search and select all rows with matches.
        n               Go to next search match.
        N               Go to previous search match.
        Space           Go to random entry.
        Left            Move to the left hand side.
        Right           Move to the right hand side.
        Shift+Left      Move to the left by half a page.
        Shift+Right     Move to the right by half a page.
        Ctrl+a          Select all.
        """.splitlines()

    def __init__(self, table, log, tags, output, user, softPath,
                 showKey, **kwargs):
        logging.basicConfig(filename=log, filemode='a', level=logging.DEBUG,
                            format='[%(asctime)s] %(levelname)s: %(message)s')
        # settings
        self.output = output
        self.n_backups = 10
        self.backup_every_n_saves = 10
        self.backup_base_name = self.output + '.backup_'
        self.saves = 0
        self.showKey = showKey
        self.tmux_split_percentage = 50
        self.log = log
        self.user = user
        self.tables = table
        self.softPath = softPath
        self.tags_file = tags
        self.column_seperator = ' '
        self.color_by = 'quality'
        self.current_tag = 'quality'
        # inits
        self.stdscr = None # curses standard screen
        self.error = ''
        self.tag_error = None
        self.last_saver_pid = None
        self.search_string = ''
        self.tags = dict()
        self.tag_data = dict()
        # init content variables
        self.df = None # the pandas data frame
        self.header = ''
        self.lines = []
        self.total_lines = 0
        self.pointer = 0
        self.selection = {self.pointer}
        self.lrpos = 0
        self.top = 0
        self.stale_lines = set()
        self.ordered_columns = []
        self.sort_columns = set()
        self.sort_reverse_columns = set()
        self.filter = dict()
        self.coloring_now = None
        self.colmap = lambda x: None
        self.in_dialog = False
        self.in_tag_dialog = False
        # init variables that get set in dialog:
        self.win = None # a curses floating window
        self.table_y0 = 0 # table position
        self.table_x0 = 0 # table position
        self.indentation = 0
        self.woffset = 0
        self.max_tag_desc_hight = 0
        self._dialog_changed = False
        self.tag_ypos = 0
        self.tag_xpos = 0
        self.col_pointer = 0
        self.tag_pointer = 0
        self.serious = False
        self.add_tag = False
        # get some data
        self.load_table()
        self.toggl_help(False)
        if not os.path.exists(self.output):
            logging.warning('The output file "%s" dose not exist '
                            'yet. Starting over...', self.output)
            self.tag_data = dict()
        else:
            with open(self.output, 'rb') as f:
                data = yaml.load(f, Loader=yaml.SafeLoader)
            if not isinstance(data, dict):
                logging.warning('The loaded %s is no dict '
                                'and will be resetted.', self.output)
                self.data = dict()
            else:
                self.data = data
        self.load_tag_definitions()
        self.reset_cols()
        self._update_now = True

    def load_tag_definitions(self):
        try:
            with open(self.tags_file, 'r') as f:
                self.tags.update(yaml.load(f, Loader=yaml.SafeLoader))
        except IOError:
            pass
        if not self.tags:
            logging.warning('The tags file "%s" could not be read. '
                            'Using default tags...', self.tags)
            self.tags = default_tags
        for tag in self.tags:
            self.tag_data.setdefault(tag, dict())
            if tag not in self.ordered_columns:
                self.ordered_columns = [tag] + self.ordered_columns

    def save_tag_definitions(self):
        temp_out = self.tags_file + '.' + self.user
        with open(temp_out, 'w') as f:
            f.write(yaml.dump(self.tags, default_flow_style=False))
        os.rename(temp_out, self.tags_file)

    def col_widths(self):
        for col in self.df.columns:
            if col in self._measured_col_width:
                yield col, self._measured_col_width[col]
            elif col in self.tags:
                yield col, self.tags[col]['col_width']
            else:
                error = f'The column {col} is not measured.'
                logging.error(error)
                self.error += error
                yield col, 10

    def load_table(self):
        if self.stdscr:
            self.stdscr.addstr(0, 0, 'Reloading the table ...')
            self.stdscr.refresh()
        else:
            print('Loading data ...')
        logging.info('Reloading the data tables.')
        try:
            table_dfs = []
            for table in self.tables:
                table_dfs.append(pd.read_csv(table, sep="\t", low_memory=False))
            self.raw_df = pd.concat(table_dfs, sort=True)
            for col in ['gse', 'id']:
                if col not in self.raw_df.columns:
                    raise Exception('The sample table needs to have the '
                                    f'column "{col}".')
            self.raw_df.index = uniquify(
                self.raw_df['gse'].str.cat(self.raw_df['id'], sep='_')
            )
            smap_counts = self.raw_df['gse'].value_counts()
            self.raw_df['n_sample'] = smap_counts[self.raw_df['gse']].values
            self._measured_col_width = dict()
            for col in self.raw_df.columns:
                l = self.raw_df[col].astype(str).map(len).quantile(.99) + 1
                self._measured_col_width[col] = int(max(l, len(col)))
                if col not in self.ordered_columns:
                    self.ordered_columns.append(col)
            self._update_now = True
        except Exception as e:
            if self.stdscr:
                logging.error('Failed loading the data tables with: %s', e)
                self.error = 'Failed loading the data tables.'
            else:
                raise

    def reset_cols(self):
        ordered_columns = ['id']
        ordered_columns += list(self.tags.keys())
        ordered_columns += [
            'n_sample',
            'gse',
            'technology',
            'status',
            'pattern',
            'col',
            'val'
        ]
        all_columns = set(self.raw_df.columns).union(set(self.tags.keys()))
        ordered_columns = [c for c in ordered_columns if c in all_columns]
        for c in all_columns:
            if c not in ordered_columns:
                ordered_columns.append(c)
        self.ordered_columns = ordered_columns
        self.show_columns = set(ordered_columns)
        self.sort_columns.add('gse')
        self.sort_reverse_columns.add('n_sample')

    def toggl_help(self, to: bool = None):
        if to is not None:
            self.print_help = to
        else:
            self.print_help = not self.print_help

    def update_df(self):
        r = self.raw_df.copy()
        data_frames = [self.raw_df.copy()]
        for col, tags in self.tag_data.items():
            tagd = pd.DataFrame.from_dict(tags, orient='index', columns=[col],
                                          dtype=locate(self.tags[col]['type']))
            data_frames.append(tagd)
        r = pd.concat(data_frames, axis=1, join='outer', sort=False)\
            .fillna(self.missing_data_value)
        for col, filter in self.filter.items():
            r = r[r[col].astype(str).str.contains(filter)]
        if self.sort_columns or self.sort_reverse_columns:
            sort_cols = self.sort_columns.union(self.sort_reverse_columns)
            sc = [c for c in self.ordered_columns if c in sort_cols]
            ascending = [True if c in self.sort_columns else False for c in sc]
            r = r.sort_values(sc, ascending=ascending)
        cols = [c for c in self.ordered_columns if c in self.show_columns]
        r = r[cols]
        if r.empty:
            logging.debug('No entries match the filter.')
            r = pd.DataFrame({
                'id': ['none'],
                'gse': ['None']
            })
        self.df = r
        if self.color_by not in r.columns:
            self.coloring_now = False
            return
        self.coloring_now = self.color_by
        tag_type = self.tags.get(self.color_by, dict()).get('type', '')
        if tag_type == 'int' or \
                pd.api.types.is_numeric_dtype(r[self.color_by].dtype):
            self.colmap = lambda x: \
                99 if x == self.missing_data_value else int(x % 10) + 1
        else:
            cmap = {key: i % 10 + 1 for i, key in
                    enumerate(sorted(set(r[self.color_by]) - {None}))}
            self.colmap = cmap.get

    def _init_curses(self):
        curses.use_default_colors()
        curses.init_pair(99, -1, -1)
        curses.init_pair(100, curses.COLOR_GREEN, -1)
        curses.init_pair(101, curses.COLOR_BLUE, -1)
        curses.init_pair(102, curses.COLOR_RED, -1)
        curses.init_pair(103, curses.COLOR_WHITE, -1)
        curses.init_pair(104, curses.COLOR_YELLOW, -1)
        curses.init_pair(105, curses.COLOR_CYAN, -1)
        for i, col in enumerate(TCOLORS):
            curses.init_pair(i + 1, col, -1)

    def _format(self, val, col, width):
        if val == self.missing_data_value:
            return ' ' * (width - 1) + self.missing_data_value
        tag_dtype = self.tags.get(col, dict()).get('type', '')
        if tag_dtype == 'int':
            if val is np.nan:
                return ' ' * (width - 1) + self.missing_data_value
            text = f'%{width}d' % val
        else:
            text = str(val).splitlines()[0]
        if len(text) > width:
            if width < 3:
                return '...'[:width]
            return text[:(width - 3)] + '...'
        return text.rjust(width)

    def _str_from_line(self, line=None):
        """ Returns string for line list and  header line if line==None. """
        if line is None:
            return self.column_seperator.join(
                self._format(col, None, w) for col, w in self.col_widths()
            )
        return self.column_seperator.join(
            self._format(l, col, w) for l, (col, w) in
            zip(line, self.col_widths())
        )

    def update_content(self):
        self.update_df()
        self._reset_lines()

    def _reset_lines(self):
        self.header = self._str_from_line()
        self.total_lines = self.df.shape[0]
        self.lines = ['-'] * self.total_lines
        self.stale_lines = set(range(self.total_lines))
        if self.pointer > self.total_lines:
            self.pointer = 0
            self.selection = {self.pointer}

    def update_lines(self, line_numbers):
        locs = set(line_numbers).intersection(self.stale_lines)
        if not locs:
            return
        ordered_locs = list(locs)
        for j in ordered_locs:
            self.lines[j] = self._str_from_line(self.df.iloc[j, :])
        self.stale_lines -= locs

    def run(self, stdscr):
        self._init_curses()
        self.stdscr = stdscr
        cn = None
        stdscr.addstr('Loading visualization ...')
        stdscr.refresh()
        while True:
            if self._update_now:
                self.update_content()
                self._update_now = False
            curses.update_lines_cols()
            padding = ' ' * curses.COLS
            nlines = curses.LINES - 4
            if self.pointer > self.total_lines - 1:
                logging.debug('Resetting pointer to 0.')
                self.pointer = 0
            self.top = self.pointer if self.pointer < self.top else self.top
            self.top = self.pointer - nlines \
                if self.pointer >= self.top + nlines else self.top
            tabcols = curses.COLS
            cols = slice(self.lrpos, self.lrpos + tabcols)
            button = self.top + nlines
            viewed_lines = range(self.top, button + 1)
            self.update_lines(viewed_lines)
            self._print_body(self.header, self.lines, nlines, cols)
            curses.setsyx(nlines + 2, 0)
            if len(self.selection) == 1:
                sel_status = str(self._id_for_index(self.pointer))
            else:
                sel_status = str(len(self.selection))
            pos = f'{self.pointer}'
            if self.total_lines > 1:
                pos += f' ({int(100*self.pointer/(self.total_lines-1))}%)'
            status_bar = [
                ('help', 'h', 100),
                ('position', pos, 100),
                ('tagging', self.current_tag, 100),
                ('selected', sel_status, 100),
            ]
            if cn and self.showKey:
                status_bar.append(('key', str(cn), 100))
            if stack().canundo():
                status_bar.append(('undoable', stack().undotext(), 100))
            if stack().canredo():
                status_bar.append(('redoable', stack().redotext(), 100))
            if self.error:
                status_bar = [('error', self.error, 102)] + status_bar
                self.error = ''
            for name, content, color in status_bar:
                name = f' {name}: '
                y, x = stdscr.getyx()
                space = curses.COLS - 1 - x
                if y < curses.LINES - 1:  # we have an extra line
                    space += curses.COLS - 1
                if len(name) > space:
                    if space < 4:
                        stdscr.addstr(' ...'[:space])
                        break
                    stdscr.addstr(name[:(space - 4)] + ' ...',
                                  curses.color_pair(color))
                    break
                stdscr.addstr(name, curses.color_pair(color))
                y, x = stdscr.getyx()
                space = curses.COLS - 1 - x
                if y < curses.LINES - 1:  # we have an extra line
                    space += curses.COLS - 1
                if content and len(content) > space:
                    if space < 4:
                        stdscr.addstr(' ...'[:space])
                        break
                    stdscr.addstr(content[:(space - 4)] + ' ...')
                    break
                stdscr.addstr(content)
            y, x = stdscr.getyx()
            stdscr.addstr(' ' * (curses.COLS - x - 1))
            if y < curses.LINES - 1:
                # clear last line
                stdscr.addstr(' ' * (curses.COLS - 1))
            if self.print_help:
                self._print_help()
            if self.in_dialog:
                self._view_dialog()
            elif self.in_tag_dialog:
                self._view_tag_dialog()
            if not self.add_tag:
                cn = self.get_key(stdscr)
            else:
                cn = b''
                self.add_tag = False
            if cn == b'q':
                break
            if self.in_dialog:
                self._dialog(cn)
            elif self.in_tag_dialog:
                self._tag_dialog(cn)
            else:
                self._react(cn, nlines, tabcols)

    def get_key(self, win):
        def get():
            try:
                return win.get_wch()
            except Exception as e:
                if str(e) != 'no input':
                    raise
                return ''
        c = get()
        try:
            cn = curses.keyname(c)
            return cn
        except TypeError:
            pass
        cn = c.encode()
        if cn != b'\x1b':
            return cn
        next_c = str(get()).encode()
        if next_c == b'[':
            # this is a Control Sequence Introducer
            while next_c in self._control_seq_parts:
                cn += next_c
                next_c = get().encode()
        return cn + next_c

    def _print_body(self, header, lines, nlines, cols, y0=0, x0=0):
        padding = ' ' * curses.COLS
        h = header + padding
        self.stdscr.addstr(y0, x0, h[cols])
        for i in range(nlines + 1):
            pos = i + self.top
            attr = curses.A_REVERSE if self.is_selected(
                pos) else curses.A_NORMAL
            if pos >= self.total_lines or pos > len(lines):
                self.stdscr.addstr(y0 + i + 1, 0, padding)
                continue
            if self.coloring_now in self.df.columns and \
                    len(self.df[self.coloring_now]) > pos:
                val = self.df[self.coloring_now].iloc[pos]
                if val is not None:
                    col = self.colmap(val)
                    attr |= curses.color_pair(col)
            text = lines[pos] + padding
            self.stdscr.addstr(y0 + i + 1, x0, text[cols], attr)

    def is_selected(self, pointer):
        return pointer in self.selection

    def _react(self, cn, nlines, tabcols):
        if cn == b'\x01':  # CTRL + a
            self.selection = set(range(self.total_lines))
        elif cn == b'h':
            self.toggl_help()
        elif cn == b'v':
            self._dialog_changed = False
            self.in_dialog = True
        elif cn == b't':
            self._dialog_changed = False
            self.load_tag_definitions()
            self.in_tag_dialog = True
        elif cn == b'l':
            self.load_table()
        elif cn == b's':
            self.stdscr.addstr(
                0, 0, 'Saving ...'.ljust(
                    curses.COLS)[:curses.COLS - 1])
            self.stdscr.refresh()
            self.save_tag_data(asynchronous=False)
        elif cn == b'o':
            os.system('tmux select-layout main-vertical')
        elif cn == b'KEY_UP':
            self.pointer -= 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif cn == b'KEY_DOWN':
            self.pointer += 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif cn == b'KEY_SR' or cn == b'\x1b[1;2A':
            old_pointer = self.pointer
            self.pointer -= 1
            self.pointer %= self.total_lines
            if self.pointer in self.selection:
                self.selection.remove(old_pointer)
            self.selection.add(self.pointer)
        elif cn == b'KEY_SF' or cn == b'\x1b[1;2B':  # Shift + Down
            old_pointer = self.pointer
            self.pointer += 1
            self.pointer %= self.total_lines
            if self.pointer in self.selection:
                self.selection.remove(old_pointer)
            self.selection.add(self.pointer)
        elif cn == b'\x1b[1;5A':  # Ctrl + Up
            tags = self.df[self.current_tag].iloc[:self.pointer + 1]
            candidates = tags.index[tags == self.missing_data_value]
            if len(candidates) > 0:
                self.pointer = self.df.index.get_loc(candidates[-1])
                self.selection = {self.pointer}
            else:
                self.error = 'No untagged entries above.'
        elif cn == b'\x1b[1;5B':  # Ctrl + Down
            tags = self.df[self.current_tag].iloc[self.pointer:]
            candidates = tags.index[tags == self.missing_data_value]
            if len(candidates) > 0:
                self.pointer = self.df.index.get_loc(candidates[0])
                self.selection = {self.pointer}
            else:
                self.error = 'No untagged entries below.'
        elif cn == b'\x1b[1;6A':  # Ctrl + Shift + Up
            tags = self.df[self.current_tag].iloc[:self.pointer + 1]
            candidates = tags.index[tags == self.missing_data_value]
            if len(candidates) > 0:
                self.pointer = self.df.index.get_loc(candidates[-1])
                self.selection.add(self.pointer)
            else:
                self.error = 'No untagged entries above.'
        elif cn == b'\x1b[1;6B':  # Ctrl + Shift + Down
            tags = self.df[self.current_tag].iloc[self.pointer:]
            candidates = tags.index[tags == self.missing_data_value]
            if len(candidates) > 0:
                self.pointer = self.df.index.get_loc(candidates[0])
                self.selection.add(self.pointer)
            else:
                self.error = 'No untagged entries below.'
        elif cn == b'g':
            xpos = 2
            ypos = 2
            hight = 1
            text = 'position:'
            width = min(curses.COLS - 2 - xpos, 10 + len(text))
            rectangle(self.stdscr, ypos - 1, xpos - 1,
                      ypos + hight, xpos + width)
            self.stdscr.addstr(ypos, xpos, text)
            editwin = self.stdscr.subwin(hight, width - len(text),
                                         ypos, xpos + len(text))
            editwin.clear()
            self.stdscr.refresh()
            box = Textbox(editwin)
            try:
                box.edit()
            except KeyboardInterrupt:
                return
            val = box.gather().strip()
            if not val.isnumeric():
                self.error = 'The entered position is not numeric.'
            else:
                self.pointer = min(self.total_lines - 1,
                                   max(0, int(float(val))))
                self.selection = {self.pointer}
        elif cn == b'G':
            xpos = 2
            ypos = 2
            hight = 1
            text = 'position (add):'
            width = min(curses.COLS - 2 - xpos, 10 + len(text))
            rectangle(self.stdscr, ypos - 1, xpos - 1,
                      ypos + hight, xpos + width)
            self.stdscr.addstr(ypos, xpos, text)
            editwin = self.stdscr.subwin(hight, width - len(text),
                                         ypos, xpos + len(text))
            editwin.clear()
            self.stdscr.refresh()
            box = Textbox(editwin)
            try:
                box.edit()
            except KeyboardInterrupt:
                return
            val = box.gather().strip()
            if not val.isnumeric():
                self.error = 'The entered position is not numeric.'
            else:
                self.pointer = min(self.total_lines - 1,
                                   max(0, int(float(val))))
                self.selection.add(self.pointer)
        elif cn == b' ':
            self.pointer = random.randint(0, self.total_lines - 1)
            self.selection = {self.pointer}
        elif cn == b'KEY_LEFT':
            if self.lrpos > 0:
                self.lrpos -= 1
        elif cn == b'KEY_SLEFT' or cn == b'\x1b[1;2D':
            self.lrpos = max(0, self.lrpos - int(tabcols / 2))
        elif cn == b'KEY_RIGHT':
            self.lrpos += 1
        elif cn == b'KEY_SRIGHT' or cn == b'\x1b[1;2C':
            self.lrpos = self.lrpos + int(tabcols / 2)
        elif cn == b'KEY_PPAGE':
            self.top = max(self.top - nlines, 0)
            self.pointer = self.top
            self.selection = {self.pointer}
        elif cn == b'KEY_NPAGE':
            top = self.top + nlines
            self.pointer = min(top, self.total_lines - 1)
            self.top = min(self.total_lines - nlines - 1, top)
            self.selection = {self.pointer}
        elif cn == b'\x1b[5;2~' or cn == 'KEY_SPREVIOUS':  # Shift + PageUp
            self.top = max(self.top - nlines, 0)
            old_pointer = self.pointer
            self.pointer = max(self.pointer - nlines, self.top)
            new_sel = iter(range(old_pointer - 1, self.pointer, -1))
            try:
                line = next(new_sel)
                if line in self.selection:
                    self.selection.remove(old_pointer)
                while line in self.selection:
                    self.selection.remove(line)
                    line = next(new_sel)
                while True:
                    self.selection.add(line)
                    line = next(new_sel)
            except StopIteration:
                pass
            self.selection.add(self.pointer)
        elif cn == b'\x1b[6;2~' or cn == 'KEY_SNEXT':  # Shift + PageDown
            top = self.top + nlines
            old_pointer = self.pointer
            self.pointer = min(old_pointer + nlines, self.total_lines - 1)
            self.top = min(self.total_lines - nlines - 1, top)
            new_sel = iter(range(old_pointer + 1, self.pointer))
            try:
                line = next(new_sel)
                if line in self.selection:
                    self.selection.remove(old_pointer)
                while line in self.selection:
                    self.selection.remove(line)
                    line = next(new_sel)
                while True:
                    self.selection.add(line)
                    line = next(new_sel)
            except StopIteration:
                pass
            self.selection.add(self.pointer)
        elif cn == b'KEY_HOME':
            self.pointer = self.top = 0
            self.selection = {self.pointer}
        elif cn == b'KEY_END':
            self.top = self.total_lines - nlines - 1
            self.pointer = self.total_lines - 1
            self.selection = {self.pointer}
        elif cn == b'u':
            if stack().canundo():
                stack().undo()
            else:
                self.error = 'Cannot undo. Manually recover one of the ' \
                             'backups instead: ' + self.backup_base_name + '*'
        elif cn == b'r' and stack().canredo():
            stack().redo()
        elif cn == b'\n':
            index = list(self.selection)
            local_df = self.df.iloc[index, :]
            gses = local_df["gse"].unique()
            files = dict()
            not_found = set()
            for gse in gses:
                file = os.path.join(self.softPath, gse, gse + '_family.soft')
                if os.path.exists(file):
                    files[gse] = file
                else:
                    logging.error('Could not find %s', file)
                    not_found.add(gse)
            max_panes = int(self.tmux_split_percentage / 10)
            if len(files) > max_panes:
                self.error = \
                    f'Cannot open more than {max_panes} panes at once. '
                return
            if not_found:
                self.error = \
                    f'Could not find soft file for {list(not_found)}. '
            for gse, file in files.items():
                logging.info('Opening %s', file)
                pane_size = int(self.tmux_split_percentage / len(files))
                ids = local_df["id"].loc[local_df["gse"] == gse].unique()
                if len(ids) > 10:
                    if self.error:
                        self.error += ' '
                    message = f'Too many samples selected for {gse}. ' \
                        'Marking only the first 10.'
                    self.error += message
                    ids = ids[:10]
                pattern = '|'.join(f'SAMPLE = {id}' for id in ids)
                less = f'less -p "{pattern}" "{file}"'
                d = 'd' if len(files) > 1 else ''
                os.system(f'tmux split-window -{d}p {pane_size} -h {less}')
        elif cn == b'd':
            self.del_tag_data(self.current_tag)
        elif cn == b'f':
            xpos = 2
            ypos = 2
            hight = 1
            text = 'pattern:'
            width = min(curses.COLS - 2 - xpos, 80 + len(text))
            rectangle(self.stdscr, ypos - 1, xpos - 1,
                      ypos + hight, xpos + width)
            self.stdscr.addstr(ypos, xpos, text)
            editwin = self.stdscr.subwin(hight, width - len(text),
                                         ypos, xpos + len(text))
            editwin.clear()
            editwin.addstr(self.search_string)
            self.stdscr.refresh()
            box = Textbox(editwin)
            try:
                box.edit()
            except KeyboardInterrupt:
                return
            self.search_string = box.gather().strip()
            cn = b'n'
        elif cn == b'F':
            xpos = 2
            ypos = 2
            hight = 1
            text = 'pattern (add all):'
            width = min(curses.COLS - 2 - xpos, 80 + len(text))
            rectangle(self.stdscr, ypos - 1, xpos - 1,
                      ypos + hight, xpos + width)
            self.stdscr.addstr(ypos, xpos, text)
            editwin = self.stdscr.subwin(hight, width - len(text),
                                         ypos, xpos + len(text))
            editwin.clear()
            editwin.addstr(self.search_string)
            self.stdscr.refresh()
            box = Textbox(editwin)
            try:
                box.edit()
            except KeyboardInterrupt:
                return
            self.search_string = box.gather().strip()
            logging.info('Searching all %s.', self.search_string)
            try:
                self.stdscr.addstr(
                    0, 0, 'Searching all ...'.ljust(
                        curses.COLS)[:curses.COLS - 1])
                self.stdscr.refresh()
                self.error = 'No match found.'
                for index, (ind, line) in enumerate(self.df.iterrows()):
                    h = line.astype(str).str.contains(self.search_string).any()
                    if not h:
                        continue
                    self.error = ''
                    self.selection.add(index)
                    self.pointer = index
            except KeyboardInterrupt:
                logging.debug('Aborting the search.')
        else:
            if self.tags[self.current_tag]['type'] == 'int' \
                    and cn in self._byte_numbers:
                # set current tag to value
                self.set_tag(self.current_tag, int(cn), self._view_state)
                return
            for tag, info in self.tags.items():
                if cn == b'\x1b' + info['key'].encode():
                    if info['type'] == 'int':
                        logging.info('Starting to tag %s.', tag)
                        self.current_tag = tag
                    elif info['type'] == 'str':
                        logging.info('Starting make a %s.', tag)
                        self.make_str(tag)
        if cn == b'n':
            self.stdscr.addstr(
                0, 0, 'Searching below ...'.ljust(
                    curses.COLS)[:curses.COLS - 1])
            self.stdscr.refresh()
            logging.info('Searching next %s.', self.search_string)
            try:
                reff = self.df.iloc[self.pointer::]
                self.error = 'No match found below.'
                for index, (ind, line) in enumerate(reff.iterrows()):
                    h = line.astype(str).str.contains(self.search_string).any()
                    if not h or index == 0:
                        continue
                    self.error = ''
                    self.pointer += index
                    self.selection = {self.pointer}
                    break
            except KeyboardInterrupt:
                logging.debug('Aborting the search.')
        elif cn == b'N':
            self.stdscr.addstr(
                0, 0, 'Searching above ...'.ljust(
                    curses.COLS)[:curses.COLS - 1])
            self.stdscr.refresh()
            logging.info('Searching previous %s.', self.search_string)
            try:
                reff = self.df.iloc[self.pointer::-1]
                self.error = 'No match found above.'
                for index, (ind, line) in enumerate(reff.iterrows()):
                    h = line.astype(str).str.contains(self.search_string).any()
                    if not h or index == 0:
                        continue
                    self.error = ''
                    self.pointer -= index
                    self.selection = {self.pointer}
                    break
            except KeyboardInterrupt:
                logging.debug('Aborting the search.')

    def make_str(self, tag):
        hight = min(23, curses.LINES - 4)
        width = min(80, curses.COLS - 4)
        editwin = curses.newwin(hight - 3, width - 3, 3, 3)
        rectangle(self.stdscr, 2, 2, hight, width)
        ids = self._id_for_index(list(self.selection))
        if len(ids) > 1:
            id = f'[{ids[0]} ...]'
        else:
            id = ids[0]
        text = f"Enter {tag} for {id}: (hit Ctrl+g to send or Ctrl+c to stop)"
        self.stdscr.addstr(2, 4, text[:(width - 4)])
        self.stdscr.refresh()
        current_texts = self.get_current_values(tag)
        if len(current_texts) > 1:
            current_text = 'different text for selection'
        elif current_texts:
            current_text = current_texts.pop()
        else:
            current_text = None
        if current_text:
            editwin.addstr(str(current_text))
        box = Textbox(editwin)
        try:
            box.edit()
        except KeyboardInterrupt:
            logging.debug('Aborded making a %s', tag)
            return
        message = box.gather().strip()
        if message:
            self.set_tag(tag, message, self._view_state)
        else:
            self.del_tag_data(tag)

    def _id_for_index(self, index):
        return self.df.index[index]

    @property
    def _view_state(self):
        return {attr: getattr(self, attr) for attr in self.view_attributes}

    @_view_state.setter
    def _view_state(self, new_state):
        for key, value in new_state.items():
            if key == 'ordered_columns' and value and isinstance(value, list) \
                    and getattr(self, 'ordered_columns', []):
                # make sure no columns are omitted
                for col in self.ordered_columns:
                    if col not in value:
                        value.append(col)
            setattr(self, key, value)
        self.total_lines = self.df.shape[0]

    @property
    def cache(self):
        return {'_view_state': self._view_state, 'version': self.__version__}

    @cache.setter
    def cache(self, cache):
        self._view_state = cache.get('_view_state')

    @property
    def data(self):
        return {
            'tag definitions': self.tags,
            'tags': self.tag_data
        }

    @data.setter
    def data(self, data):
        self.tag_data = data.get('tags', dict())
        self.tags.update(data.get('tag definitions', dict()))
        for tag in self.tags:
            self.tag_data.setdefault(tag, dict())

    def get_current_values(self, tag):
        selection = list(self.selection)
        ids = self._id_for_index(selection)
        td = self.tag_data[tag]
        return {td[id] for id in ids if id in td}

    @undoable
    def del_tag_data(self, tag):
        view_state = self._view_state
        lselected = list(self.selection)
        ids = self._id_for_index(lselected)
        td = self.tag_data[tag]
        current = {id: td.get(id) for id in ids}
        if len(ids) == 1:
            id = next(iter(ids))
            long_desc = f'removing tag data "{tag}" for {id}'
            short_desc = f'delete {tag} for {id}'
        else:
            lids = list(ids)
            long_desc = f'removing tag data "{tag}" for {lids}'
            short_desc = f'delete {tag} for [{lids[0]}, ...]'
        logging.info(long_desc)
        for id in ids:
            td.pop(id, None)
        df_data = False
        if tag in self.df.columns:
            df_data = True
            old_df = self.df.loc[self.df.index[lselected], tag]
            self.df.loc[self.df.index[lselected], tag] = self.missing_data_value
        self.save_tag_data()
        self.stale_lines.update(self.selection)
        yield short_desc
        logging.info('undoing %s', long_desc)
        for id, v in current.items():
            if v is None or v is np.nan:
                td.pop(id, None)
            else:
                td[id] = v
        self.save_tag_data()
        self._view_state = view_state
        if df_data:
            self.df.loc[self.df.index[lselected], tag] = old_df
        self._reset_lines()

    @undoable
    def set_tag(self, tag, val, view_state):
        self._view_state = view_state
        lselected = list(self.selection)
        ids = self._id_for_index(lselected)
        td = self.tag_data[tag]
        current = {id: td.get(id) for id in ids}
        if self.tags[tag]['type'] == 'str':
            log_val = val.splitlines()[0]
            if len(log_val) > 20:
                log_val = log_val[:17] + '...'
        else:
            log_val = val
        if len(ids) == 1:
            id = next(iter(ids))
            long_desc = f'setting tag "{tag}" to "{log_val}" for {id}'
            short_desc = f'{tag}={log_val} for {id}'
        else:
            lids = list(ids)
            long_desc = f'setting tag "{tag}" to "{log_val}" for {lids}'
            short_desc = f'{tag}={log_val} for [{lids[0]}, ...]'
        logging.info(long_desc)
        for id in ids:
            td[id] = val
        df_data = False
        if tag in self.df.columns:
            df_data = True
            old_df = self.df.loc[self.df.index[lselected], tag]
            self.df.loc[self.df.index[lselected], tag] = val
        self.save_tag_data()
        self.stale_lines.update(self.selection)
        yield short_desc
        logging.info('undoing %s', long_desc)
        for id, v in current.items():
            if v is None or v is np.nan:
                td.pop(id, None)
            else:
                td[id] = v
        self.save_tag_data()
        self._view_state = view_state
        if df_data:
            self.df.loc[self.df.index[lselected], tag] = old_df
        self._reset_lines()

    def save_tag_data(self, asynchronous=True):
        previous = self.last_saver_pid
        if asynchronous:
            self.last_saver_pid = os.fork()
        if not asynchronous and previous:
            # we can wait for previous save
            try:
                _, exit_code = os.waitpid(previous, 0)
            except ChildProcessError:
                pass
        if not asynchronous or self.last_saver_pid == 0:
            save = self.data
            # Waiting does not work since children never die.
            # This is likely due to curses.wrapper.
            dt = datetime.today().strftime('%Y-%m-%d-%H:%M:%S')
            if self.saves % self.backup_every_n_saves == 0:
                backup_name = self.backup_base_name + dt
                logging.info('Writing backup %s', backup_name)
                try:
                    os.rename(self.output, backup_name)
                except FileNotFoundError:
                    pass
                except BaseException as e:
                    err = 'Could not write backup: ' + str(e)
                    self.error += err
                    logging.error(err)
                written = sorted(glob.glob(self.backup_base_name + '*'))
                if len(written) > self.n_backups:
                    logging.info('Deleting old backup %s', written[0])
                    try:
                        os.unlink(written[0])
                    except BaseException as e:
                        err = 'Could not delete old backup: ' + str(e)
                        self.error += ' ' + err
                        logging.error(err)
            tmp_name = self.output + '.tmp' + dt
            try:
                with open(tmp_name, 'w') as f:
                    f.write(yaml.dump(save, default_flow_style=False))
                os.rename(tmp_name, self.output)
            except BaseException as e:
                err = 'Could not write tag data: ' + str(e)
                self.error += ' ' + err
                logging.error(err)
                try:
                    os.remove(tmp_name)
                except BaseException:
                    pass
                if asynchronous:
                    os._exit(1)
            if asynchronous:
                os._exit(0)

        self.saves += 1

    def _print_help(self):
        help = self.helptext
        hight = min(len(help) + 1, curses.LINES - 4)
        text_width = max(len(line) for line in help)
        width = min(text_width + 8, curses.COLS - 4)
        self.win = self.stdscr.subwin(hight, width, 2, 2)
        self.win.clear()
        self.win.border()
        for i in range(1, hight - 1):
            self.win.addstr(i, 5, help[i][:width - 6])
        if hight - 1 < len(help):
            self.win.addstr(i, 1, ' ' * (width - 2))
            self.win.addstr(i, 5, '...'[:width - 6])

    def _view_dialog(self):
        self.table_y0 = 5
        self.table_x0 = 6
        hight = min(len(self.ordered_columns) +
                    self.table_y0 + 2, curses.LINES - 4)
        width = min(self._window_width, curses.COLS - 4)
        self.win = self.stdscr.subwin(hight, width, 2, 2)
        self.win.clear()
        self.win.border()
        buttons = {
            'v': 'exit',
            'Enter': 'edit regex',
            'r': 'reset',
            'd': 'toggle deactivate',
            's': 'toggle sort by',
            'c': 'toggle color by',
            'shift+up/down': 'change order'
        }
        self.win.move(1, self.table_x0 - 2)
        for key, desc in buttons.items():
            hintlen = len(key) + len(desc) + 4
            _, x = self.win.getyx()
            if x + hintlen > width - 2:
                break
            self.win.addstr('  ')
            self.win.addstr(key + ':', curses.color_pair(100))
            self.win.addstr(' ' + desc)
        legend = {
            'legend:': 103,
            'deactivated': 102,
            'sorted': 101,
            'reverse sorted': 105,
            'colored': 104
        }
        self.win.move(2, self.table_x0 - 2)
        for lable, col in legend.items():
            hintlen = len(lable) + 2
            _, x = self.win.getyx()
            if x + hintlen > width - 2:
                break
            self.win.addstr('  ')
            self.win.addstr(lable, curses.color_pair(col))
        self.indentation = max(len(c) for c in self.ordered_columns)
        ind = width - self.table_x0 - 1 if width - 1 > self.table_x0 else 0
        header = 'column' + ' ' * (self.indentation - 5) + 'regex'
        self.win.addstr(4, self.table_x0, header[:ind])
        self.woffset = max(0, self.col_pointer - hight + self.table_y0 + 3)
        for i, col in enumerate(self.ordered_columns):
            if i < self.woffset:
                continue
            elif self.woffset > 0 and i == self.woffset:
                self.win.addstr(self.table_y0, self.table_x0, '...'[:ind])
                continue
            ypos = i + self.table_y0 - self.woffset
            if ypos + 2 == hight:
                self.win.addstr(ypos, self.table_x0, '...'[:ind])
                break
            attr = curses.A_REVERSE if i == self.col_pointer else curses.A_NORMAL
            if col not in self.show_columns:
                attr |= curses.color_pair(legend['deactivated'])
            elif col == self.color_by:
                attr |= curses.color_pair(legend['colored'])
            elif col in self.sort_columns:
                attr |= curses.color_pair(legend['sorted'])
            elif col in self.sort_reverse_columns:
                attr |= curses.color_pair(legend['reverse sorted'])
            filter = self.filter.get(col, '.*')
            text = col + ' ' * (self.indentation - len(col) + 1) + filter
            self.win.addstr(ypos, self.table_x0, text[:ind], attr)
            if col in self.tag_data:
                self.win.addstr(ypos, 2, 'tag')

    def _dialog(self, cn):
        if cn == b'v':
            self.in_dialog = False
            self.stdscr.addstr(
                0, 0, 'Loading ...'.ljust(
                    curses.COLS)[:curses.COLS - 1])
            self.stdscr.refresh()
            if self._dialog_changed:
                self._update_now = True
        elif cn == b'\n':
            col = self.ordered_columns[self.col_pointer]
            ypos = self.col_pointer + self.table_y0 - self.woffset + 2
            xpos = self.indentation + self.table_x0 + 3
            width = self._window_width - xpos
            editwin = self.stdscr.subwin(1, width, ypos, xpos)
            editwin.addstr(0, 0, self.filter.get(col, ''))
            self.stdscr.refresh()
            box = Textbox(editwin)
            box.edit()
            filter = box.gather().strip()
            if filter not in ['*', '']:
                logging.info('Setting filter for "%s": "%s"', col, filter)
                self.filter[col] = filter
            else:
                logging.info('Setting empty filter for "%s".', col)
                self.filter.pop(col, None)
            self._dialog_changed = True
        elif cn == b'KEY_UP':
            self.col_pointer -= 1
            self.col_pointer %= len(self.ordered_columns)
        elif cn == b'KEY_DOWN':
            self.col_pointer += 1
            self.col_pointer %= len(self.ordered_columns)
        elif cn == b'r':
            col = self.ordered_columns[self.col_pointer]
            logging.info('Resetting filter for "%s".', col)
            if col in self.filter:
                self.filter.pop(col, None)
                self._dialog_changed = True
        elif cn == b'd':
            col = self.ordered_columns[self.col_pointer]
            if col in self._required_columns:
                logging.debug('Cannot deactivate "%s".', col)
            elif col in self.show_columns:
                logging.info('Deactivate "%s".', col)
                self.show_columns.remove(col)
            else:
                logging.info('Activate "%s".', col)
                self.show_columns.add(col)
            self._dialog_changed = True
        elif cn == b's':
            col = self.ordered_columns[self.col_pointer]
            if col in self.sort_columns:
                logging.info('Reverse sort by "%s".', col)
                self.sort_columns.remove(col)
                self.sort_reverse_columns.add(col)
            elif col in self.sort_reverse_columns:
                logging.info('Do not sort by "%s".', col)
                self.sort_reverse_columns.remove(col)
            else:
                logging.info('Sort by "%s".', col)
                self.sort_columns.add(col)
            self._dialog_changed = True
        elif cn == b'KEY_SR' or cn == b'\x1b[1;2A':
            col_val = self.ordered_columns[self.col_pointer]
            logging.info('Moving column "%s" up.', col_val)
            col_pos = self.col_pointer
            self.col_pointer -= 1
            if self.col_pointer < 0:
                self.col_pointer = len(self.ordered_columns) - 1
                self.ordered_columns.remove(col_val)
                self.ordered_columns.append(col_val)
            else:
                self.ordered_columns[col_pos] = \
                    self.ordered_columns[self.col_pointer]
                self.ordered_columns[self.col_pointer] = col_val
                self._dialog_changed = True
        elif cn == b'KEY_SF' or cn == b'\x1b[1;2B':  # Shift + Down
            col_val = self.ordered_columns[self.col_pointer]
            logging.info('Moving column "%s" down.', col_val)
            col_pos = self.col_pointer
            self.col_pointer += 1
            if self.col_pointer >= len(self.ordered_columns):
                self.col_pointer = 0
                self.ordered_columns.remove(col_val)
                self.ordered_columns = [col_val] + self.ordered_columns
                del self.ordered_columns[-1]
            else:
                self.ordered_columns[col_pos] = \
                    self.ordered_columns[self.col_pointer]
                self.ordered_columns[self.col_pointer] = col_val
                self._dialog_changed = True
        elif cn == b'c':
            col = self.ordered_columns[self.col_pointer]
            logging.info('Coloring by "%s".', col)
            if self.color_by == col:
                self.color_by = False
            else:
                self.color_by = col
            self._dialog_changed = True

    def _view_tag_dialog(self):
        self.table_y0 = 4
        self.table_x0 = 2
        self.max_tag_desc_hight = min(self.tag_description_max_hight,
                                      curses.LINES - self.table_x0 - 6)
        content_hight = 0
        obove_selected_hight = 0
        content_ypos = list()
        self.tag_pointer %= len(self.tags) + self.add_tag
        for i, (tag, info) in enumerate(sorted(self.tags.items())):
            content_hight += info['desc'].count('\n') + 1
            content_ypos.append(content_hight)
            if i < self.tag_pointer:
                obove_selected_hight = content_hight
            if i == self.tag_pointer:
                selection_hight = info['desc'].count('\n') + 1
        if i < self.tag_pointer:
            # pointed on a new tag
            content_hight += self.max_tag_desc_hight
            selection_hight = self.max_tag_desc_hight
        hight = min(content_hight + self.table_y0 + 2, curses.LINES - 4)
        width = min(self._window_width, curses.COLS - 4)
        table_capacity = hight - self.table_y0 - 4
        if self.tag_pointer >= i:
            # the last entry is selected and no space for "..." needed
            table_capacity += 1
        if selection_hight > table_capacity:
            self.woffset = obove_selected_hight - 1
        else:
            self.woffset = obove_selected_hight + selection_hight - table_capacity - 1
        self.woffset = max(0, self.woffset)
        self.win = self.stdscr.subwin(hight, width, 2, 2)
        self.win.clear()
        self.win.border()
        buttons = {
            't': 'exit',
            'Enter': 'edit tag',
            'n': 'new tag',
            'd': 'delete tag',
            'u': 'undo',
            'r': 'redo'
        }
        self.win.move(1, self.table_x0 - 1)
        for key, desc in buttons.items():
            hintlen = len(key) + len(desc) + 4
            _, x = self.win.getyx()
            if x + hintlen > width - 2:
                break
            self.win.addstr(' ')
            self.win.addstr(key + ':', curses.color_pair(100))
            self.win.addstr(' ' + desc)
        if self.tag_error:
            self.win.addstr(2, self.table_x0, self.tag_error,
                            curses.color_pair(102))
            self.tag_error = None
        self.indentation = {'name': max(len(c) for c in self.tags)}
        header = 'name'.ljust(self.indentation['name'])
        for tc in TAG_CHARS:
            field_len = max(len(str(v[tc])) for v in self.tags.values())
            field_len = max(len(tc), field_len)
            header += ' ' + tc.ljust(field_len)
            self.indentation[tc] = field_len
        ind = width - self.table_x0 - 1 if width - 1 > self.table_x0 else 0
        self.win.addstr(3, self.table_x0, header[:ind])
        ypos = self.table_y0 - self.woffset
        if self.woffset > 0:
            self.win.addstr(self.table_y0, self.table_x0, '...'[:ind])
        self.tag_ypos = None
        for i, (tag, info) in enumerate(sorted(self.tags.items())):
            if self.woffset > 0 and ypos <= self.table_y0:
                ypos += info['desc'].count('\n') + 1
                continue
            if ypos + 2 >= hight:
                self.win.addstr(ypos, self.table_x0, '...'[:ind])
                break
            if i == self.tag_pointer:
                attr = curses.A_REVERSE
                self.tag_ypos = ypos
            else:
                attr = curses.A_NORMAL
            text = tag.ljust(self.indentation['name'])
            desc_lines = info.get('desc', '').splitlines()
            for tc in TAG_CHARS:
                indent = self.indentation[tc]
                if tc != 'desc':
                    content = str(self.tags[tag].get(tc, ''))
                    text += ' ' + content.ljust(indent)
                else:
                    x_desc_start = len(text) + 1
                    text += ' ' + desc_lines[0].ljust(indent)
            self.win.addstr(ypos, self.table_x0, text[:ind], attr)
            ypos += 1
            for k, line in enumerate(desc_lines):
                if k == 0:
                    continue
                if ypos + 2 >= hight:
                    self.win.addstr(ypos, self.table_x0, '...'[:ind])
                    break
                text = ' ' * x_desc_start + \
                    line.ljust(self.indentation['desc'])
                self.win.addstr(ypos, self.table_x0, text[:ind], attr)
                ypos += 1
        if self.tag_ypos is None:
            # we musst be on a new line
            self.tag_ypos = ypos
        if self.add_tag:
            try:
                self._tag_edit()
            except KeyboardInterrupt:
                pass

    def _tag_dialog(self, cn):
        if self.serious and cn != b'd':
            self.serious = False
        if cn == b't':
            self.in_tag_dialog = False
            self.stdscr.addstr(
                0, 0, 'Loading ...'.ljust(
                    curses.COLS)[:curses.COLS - 1])
            self.stdscr.refresh()
        elif cn == b'\n':
            for i, tag in enumerate(sorted(self.tags)):
                if i == self.tag_pointer:
                    break
            try:
                self._tag_edit(tag)
            except KeyboardInterrupt:
                pass
        elif cn == b'n':
            self.tag_pointer = len(self.tags)
            self.add_tag = True
        elif cn == b'd':
            for i, tag in enumerate(sorted(self.tags)):
                if i == self.tag_pointer:
                    break
            if self.tag_data.get(tag) and not self.serious:
                self.tag_error = f'The tag {tag} contains data. ' \
                                 'Hit d again if you realy want to delete it.'
                self.serious = True
            else:
                self.remove_tag(tag)
                self.serious = False
        elif cn == b'KEY_UP':
            self.tag_pointer -= 1
            self.tag_pointer %= len(self.tags)
        elif cn == b'KEY_DOWN':
            self.tag_pointer += 1
            self.tag_pointer %= len(self.tags)
        elif cn == b'u' and stack().canundo():
            stack().undo()
        elif cn == b'r' and stack().canredo():
            stack().redo()

    def _tag_edit(self, tag_name=None):
        info = self.tags.get(tag_name, dict())
        if tag_name is None:
            tag_name = ''
        ypos = self.tag_ypos + 2
        xpos = self.table_x0 + 2
        total_width = min(self._window_width, curses.COLS - 4)
        ind = total_width - xpos if total_width > xpos else 0

        def print_status(status, color=101):
            self.stdscr.addstr(4, self.table_x0 + 2, status.ljust(ind)[:ind],
                               curses.color_pair(color))
            self.stdscr.refresh()

        def get_value(default, no_get=False, hight=1):
            width = total_width - xpos
            if not no_get:
                editwin = self.stdscr.subwin(hight, width, ypos, xpos)
                editwin.clear()
                if hight > 1:
                    rectangle(self.stdscr, ypos - 1, xpos - 1,
                              ypos + hight, xpos + width)
                    for i, line in enumerate(default.splitlines()):
                        if i + 1 > hight:
                            break
                        editwin.addstr(i, 0, line[:width])
                else:
                    editwin.addstr(0, 0, default[:width])
                self.stdscr.refresh()
                box = Textbox(editwin)
                box.edit()
                return box.gather().strip()
            else:
                for i, line in enumerate(default.splitlines()):
                    if i + 1 > hight:
                        break
                    self.stdscr.addstr(ypos + i, xpos, line[:width])
        if not tag_name:
            print_status('Enter a name! (Ctrl+c to stop)')
            while True:
                tag_name = get_value(tag_name)
                if not tag_name or tag_name in self.tags.keys():
                    print_status('Enter an unused name! (Ctrl+c to stop)', 102)
                else:
                    break
        xpos += self.indentation['name'] + 1
        new_info = dict()
        get_value(self.user, no_get=True)
        new_info['editor'] = self.user
        xpos += self.indentation['editor'] + 1
        print_status('Hit a letter key! (Ctrl+c to stop)')
        used_keyes = {t['key'] for t in self.tags.values()}
        current_key = info.get('key', '')
        used_keyes -= {current_key}
        while True:
            self.stdscr.addstr(ypos, xpos, current_key)
            self.stdscr.refresh()
            key = self.stdscr.getkey(ypos, xpos)
            if key == '\n':
                key = current_key
            if key in used_keyes:
                print_status('Hit an unused letter key! (Ctrl+c to stop)', 102)
            elif key in 'abcdefghijklmnopqrstuvwxyz' and key != '':
                break
            else:
                print_status('Hit a letter key! (Ctrl+c to stop)', 102)
        new_info['key'] = key
        self.stdscr.addstr(ypos, xpos, key)
        xpos += self.indentation['key'] + 1
        print_status('Enter a type!  (Ctrl+c to stop)')
        ct = info.get('type', '')
        if not ct:
            while True:
                ct = get_value(ct)
                if ct in ['int', 'str']:
                    break
                print_status('Please enter "int" for integer or "str" '
                             'for string!  (Ctrl+c to stop)', 102)
        new_info['type'] = ct
        xpos += self.indentation['type'] + 1
        print_status('Enter a column width! (Ctrl+c to stop)')
        cw = info.get('col_width', '')
        while True:
            cw = get_value(str(cw))
            if cw.isnumeric() and int(float(cw)) > 0:
                break
            print_status('Please enter a positive integer!  (Ctrl+c to stop)',
                         102)
        new_info['col_width'] = int(cw)
        xpos += self.indentation['col_width'] + 1
        print_status('Enter a description! '
                     '(hit Ctrl+g to send or Ctrl+c to stop)')
        while True:
            new_info['desc'] = get_value(info.get('desc', ''),
                                         hight=self.max_tag_desc_hight)
            if not new_info['desc']:
                print_status('Enter a description! '
                             '(hit Ctrl+g to send or Ctrl+c to stop)', 102)
            else:
                break
        self.set_tag_definition(tag_name, new_info)

    @undoable
    def set_tag_definition(self, tag_name, new_info):
        old_info = self.tags.get(tag_name)
        self.tags[tag_name] = new_info
        if old_info is None:
            self.tag_data.setdefault(tag_name, dict())
            self.ordered_columns = [tag_name] + self.ordered_columns
            self.show_columns.add(tag_name)
            self.df.insert(0, tag_name, self.missing_data_value)
            desc = f'create tag {tag_name}.'
        else:
            desc = f'edit tag {tag_name}.'
        self._reset_lines()
        logging.info(desc)
        self.save_tag_definitions()
        for i, tag in enumerate(sorted(self.tags)):
            self.tag_pointer = i
            if tag == tag_name:
                break
        yield desc
        logging.info('undoing %s', desc)
        if old_info is None:
            self.ordered_columns.remove(tag_name)
            self.show_columns.remove(tag_name)
            del self.tags[tag_name]
            del self.tag_data[tag_name]
            del self.df[tag_name]
        else:
            self.tags[tag_name] = old_info
        self.header = self._str_from_line()
        self._reset_lines()
        self.save_tag_definitions()
        for i, tag in enumerate(sorted(self.tags)):
            self.tag_pointer = i
            if tag == tag_name:
                break

    @undoable
    def remove_tag(self, tag_name):
        old_def = self.tags[tag_name]
        old_data = self.tag_data[tag_name]
        del self.tags[tag_name]
        del self.tag_data[tag_name]
        self.show_columns -= {tag_name}
        self.ordered_columns.remove(tag_name)
        df_dat = None
        if tag_name in self.df:
            df_dat = self.df[tag_name]
            del self.df[tag_name]
            self._reset_lines()
        desc = f'remove tag {tag_name}'
        logging.info(desc)
        self.save_tag_definitions()
        self.tag_pointer %= len(self.tags)
        yield desc
        logging.info('undoing %s', desc)
        self.tags[tag_name] = old_def
        self.tag_data[tag_name] = old_data
        self.ordered_columns = [tag_name] + self.ordered_columns
        self.show_columns.add(tag_name)
        self.df.insert(0, tag_name, self.missing_data_value)
        if df_dat is not None:
            self.df[tag_name] = df_dat
        self.header = self._str_from_line()
        self._reset_lines()
        self.save_tag_definitions()
        for i, tag in enumerate(sorted(self.tags)):
            self.tag_pointer = i
            if tag == tag_name:
                break

    @property
    def helptext(self):
        h = [line.strip() for line in self._helptext]
        indent = 16
        for tag, info in self.tags.items():
            keys = 'Alt+' + info['key']
            space = ' ' * max(1, indent - len(keys))
            if info['type'] == 'str':
                h.append(keys + space + 'Make a ' + tag + '.')
            else:
                h.append(keys + space + 'Start tagging ' + tag + '.')
        h.append('')
        h.append('Log:')
        h.append(self.log)
        return h
