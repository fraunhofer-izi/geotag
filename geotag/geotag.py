import os
import dill
import argparse
import pandas as pd
import numpy as np
import curses
from curses.textpad import Textbox, rectangle
import time
import locale
import logging
import yaml
from .undo import stack, undoable

# use system default localization
locale.setlocale(locale.LC_ALL, 'C')
code = locale.getpreferredencoding()

def main():
    desc = 'Interface to quickly tag geo data sets.'
    parser = argparse.ArgumentParser(description=desc,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--rnaSeq',
                        help='.RDS table containing the extraction status of '
                        'RNASeq studies.', type=str, metavar='path',
                        #default='/mnt/ribolution/user_worktmp/dominik.otto/'
                        #'tumor-deconvolution-dream-challenge/'
                        #'extraction_stats_head.tsv')
                        default="/home/dominik/rn_home/dominik.otto/Projects/"
                        "geotag/data/extraction_stats.tsv")
    parser.add_argument('--array',
                        help='.RDS table containing the extraction status of '
                        'microarray studies.', type=str, metavar='path',
                        #default='/mnt/ribolution/user_worktmp/dominik.otto/'
                        #'tumor-deconvolution-dream-challenge/'
                        #'extraction_stats_array.tsv')
                        default="/home/dominik/rn_home/dominik.otto/Projects/"
                        "geotag/data/extraction_stats_array.tsv")
    parser.add_argument('--user',
                        help='The user name under which to write tags and log.',
                        type=str, metavar='name',
                        default=os.environ['USER'])
    parser.add_argument('--log',
                        help='The file path for the log.',
                        type=str, metavar='path',
                        default="/home/dominik/rn_home/dominik.otto/Projects/"
                        f"geotag/data/{os.environ['USER']}.log")
    parser.add_argument('--tags',
                        help='The file path for the tag yaml.',
                        type=str, metavar='path.yml',
                        default="/home/dominik/rn_home/dominik.otto/Projects/"
                        f"geotag/data/tags.yaml")
    parser.add_argument('--output',
                        help='The output file path.',
                        type=str, metavar='path.yml',
                        default="/home/dominik/rn_home/dominik.otto/Projects/"
                        f"geotag/data/{os.environ['USER']}.yml")
    parser.add_argument('--state',
                        help='Path to a cached state of geotag.',
                        type=str, metavar='path.pkl',
                        default="/home/dominik/rn_home/dominik.otto/Projects/"
                        f"geotag/data/{os.environ['USER']}.pkl")
    parser.add_argument('--update',
                        help='Overwrite the cache.',
                        action="store_true")
    args = parser.parse_args()
    if not args.update and os.path.exists(args.state):
        try:
            with open(args.state, 'rb') as f:
                app = dill.load(f)
        except Exception as e:
            print('Failed to load previos state. Pass --update to overwrite.')
            raise
        if app.__version__ != App.__version__:
            raise Exception(f'The geotag version "{App.__version__}" differs '
                    f'from version of the cache "{app.__version__}". '
                    'Pass the parameter --update if you want to overwrite it.')
        if app.array != args.array:
            raise Exception(f'The sellected array db "{args.array}" differs '
                            f'from the one saved in state "{app.array}".'
                            'Pass the parameter --update if you want to '
                            'overwrite the stae.')
        if app.rnaSeq != args.rnaSeq:
            raise Exception(f'The sellected rnaSeq db "{args.rnaSeq}" differs '
                            f'from the one saved in state "{app.rnaSeq}".'
                            'Pass the parameter --update if you want to '
                            'overwrite the stae.')
        app.log = args.log
        app.output = args.output
        app.tags = args.tags
        app.user = args.user
    else:
        app = App(**vars(args))
    try:
        curses.wrapper(app.run)
    finally:
        print('Saving cache...')
        for attr in ['stdscr', 'win']:
            try:
                delattr(app, attr)
            except AttributeError:
                pass
        with open(args.state, 'wb') as f:
            dill.dump(app, f)

tcolors = [196, 203, 202, 208, 178, 148, 106, 71, 31, 26]
default_tags = {
    'quality':{
        'type':int,
        'desc':'From 0 to 9.',
        'key':b'\x1bq',
        'col_width':8
    },
    'note':{
        'type':str,
        'desc':'A note.',
        'key':b'\x1bn',
        'col_width':20
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

def keypartmap(c):
    if c == 27:
        return 'Alt'
    else:
        return chr(c)

class App:
    __version__ = '0.0.1'

    def __init__(self, rnaSeq, array, log, tags, output, **kwargs):
        logging.basicConfig(filename=log, filemode='a', level=logging.DEBUG,
                format='[%(asctime)s] %(levelname)s: %(message)s')
        self.array = array
        self.rnaSeq = rnaSeq
        self.output = output
        self.tags_file = tags
        rnaSeq_df = pd.read_csv(self.rnaSeq, sep="\t", low_memory=False)
        array_df = pd.read_csv(self.array, sep="\t", low_memory=False)
        self.raw_df = pd.concat([rnaSeq_df, array_df])
        self.raw_df.index = uniquify(self.raw_df['id'])
        self._measured_col_width = dict()
        for col in self.raw_df.columns:
            l = self.raw_df[col].astype(str).map(len).quantile(.99)
            self._measured_col_width[col] = int(min(20, max(l, len(col))))
        self.sort_columns = set()
        self.filter = dict()
        self.toggl_help(False)
        self.in_dialog = False
        self.pointer = 0
        self.col_pointer = 0
        self.selection = {self.pointer}
        self.lrpos = 0
        self.top = 0
        self.last_saver_pid = None
        self.color_by = 'quality'
        self.current_tag = 'quality'
        if not os.path.exists(tags):
            logging.warning(f'The tags file "{tags}" dose not exist. '
                           'Using default tags...')
            self.tags = default_tags
        else:
            with open(self.tags_file, 'rb') as f:
                self.tags = yaml.load(f, Loader=yaml.SafeLoader)
        if not os.path.exists(self.output):
            logging.warning(f'The output file "{self.output}" dose not exist '
                            'yet. Starting over...')
            self.tag_data = dict()
        else:
            with open(self.output, 'rb') as f:
                self.tag_data = yaml.load(f, Loader=yaml.SafeLoader)
            if not isinstance(self.tag_data, dict):
                logging.warning(f'The loaded {self.output} is no dict '
                                'and will be resetted.')
                self.tag_data = dict()
        for tag in self.tags:
            self.tag_data.setdefault(tag, dict())
        self.reset_cols()
        self._update_now = True

    def col_widths(self):
        for col in self.df.columns:
            if col in self._measured_col_width:
                yield col, self._measured_col_width[col]
            elif col in self.tags:
                yield col, self.tags[col]['col_width']

    def reset_cols(self):
        self.ordered_columns = ['id']
        self.ordered_columns += list(self.tags.keys())
        self.ordered_columns += [
            'gse',
            'technology',
            'status',
            'coarse.cell.type',
            'fine.cell.type',
            'pattern',
            'col',
            'val'
        ]
        all_columns = list(self.raw_df.columns) + list(self.tags.keys())
        for col in self.ordered_columns:
            if col not in all_columns:
                self.ordered_columns.remove(col)
        self.show_columns = set(self.ordered_columns)
        for col in all_columns:
            if col not in self.ordered_columns:
                self.ordered_columns.append(col)

    def toggl_help(self, to: bool=None):
        if to is not None:
            self.print_help = to
        else:
            self.print_help = not self.print_help

    def update_df(self):
        r = self.raw_df.copy()
        data_frames = [self.raw_df.copy()]
        for col, tags in self.tag_data.items():
            tagd = pd.DataFrame.from_dict(tags, orient='index', columns=[col],
                                          dtype=self.tags[col]['type'])
            data_frames.append(tagd)
        r = pd.concat(data_frames, axis=1, join='outer').fillna('-')
        for col, filter in self.filter.items():
            r = r[r[col].astype(str).str.contains(filter)]
        if self.sort_columns:
            sc = [c for c in self.ordered_columns if c in self.sort_columns]
            r = r.sort_values(sc)
        cols = [c for c in self.ordered_columns if c in self.show_columns]
        r = r[cols]
        if r.empty:
            logging.debug('No entries match the filter.')
            r = pd.DataFrame({
                'id':['none'],
                'error':['No entries match the filter.']
            })
        self.df = r
        if self.color_by not in r.columns:
            self.coloring_now = False
            return
        self.coloring_now = self.color_by
        is_numeric_tag = self.tags.get(self.color_by, dict()).get('type') is int
        if is_numeric_tag or \
                pd.api.types.is_numeric_dtype(r[self.color_by].dtype):
            self.colmap = lambda x: 99 if x=='-' else int(x%10)+1
        else:
            cmap = {key:i%10+1 for i, key in
                    enumerate(sorted(set(r[self.color_by])-{None}))}
            self.colmap = cmap.get

    @property
    def formatters(self):
        cws = dict(self.col_widths())
        formatters = list()
        def int_formatter(s, width):
            if s=='-':
                return ' '*(width-1)+'-'
            text = f'%{width}d' % s
            if len(text)>width:
                return text[:(width-3)]+'...'
            return text
        def str_formatter(s, width):
            text = str(s).splitlines()[0]
            if len(text)>width:
                return text[:(width-3)]+'...'
            return text.rjust(width)
        for col in self.df.columns:
            width = int(cws[col])
            logging.debug(f'{col} with {width}')
            tag_dtype = self.tags.get(col, dict()).get('type')
            if tag_dtype is int:
                formatters.append(lambda s: int_formatter(s, width))
            else:
                formatters.append(lambda s: str_formatter(s, width))
        return formatters

    def get_lines(self, lines):
        rdf = self.df.iloc[lines, :]
        return rdf.to_string(index=False, header=False,
                             formatters=self.formatters).splitlines()

    def _init_curses(self):
        curses.use_default_colors()
        curses.init_pair(99, -1, -1)
        curses.init_pair(100, curses.COLOR_GREEN, -1)
        curses.init_pair(101, curses.COLOR_BLUE, -1)
        curses.init_pair(102, curses.COLOR_RED, -1)
        curses.init_pair(103, curses.COLOR_WHITE, -1)
        curses.init_pair(104, curses.COLOR_YELLOW, -1)
        for i, col in enumerate(tcolors):
            curses.init_pair(i+1, col, -1)

    def update_content(self):
        self.update_df()
        one_line = self.df.iloc[:1, :]
        lines = one_line.to_string(index=False, header=True,
                                   formatters=self.formatters).splitlines()
        self.header = ''.join(col.rjust(w) for col, w in self.col_widths())
        self.total_lines = self.df.shape[0]
        self.lines = list(range(self.total_lines))
        self.stale_lines = set(range(self.total_lines))
        if self.pointer > self.total_lines:
            self.pointer = 0
            self.selection = {self.pointer}

    def update_lines(self, line_numbers):
        locs = set(line_numbers).intersection(self.stale_lines)
        if locs:
            ordered_locs = list(locs)
            new_lines = self.get_lines(ordered_locs)
            for i, j in enumerate(ordered_locs):
                self.lines[j] = new_lines[i]
            self.stale_lines -= locs

    def run(self, stdscr):
        self._init_curses()
        self.stdscr = stdscr
        cn = None
        stdscr.addstr('Loading...')
        stdscr.refresh()
        while True:
            if self._update_now:
                self.update_content()
                self._update_now = False
            curses.update_lines_cols()
            padding = ' '*curses.COLS
            nlines = curses.LINES-4
            self.top = self.pointer if self.pointer < self.top else self.top
            self.top = self.pointer - nlines \
                    if self.pointer >= self.top + nlines else self.top
            tabcols = curses.COLS
            cols = slice(self.lrpos, self.lrpos+tabcols)
            button = self.top + nlines
            viewed_lines = range(self.top, button+1)
            self.update_lines(viewed_lines)
            self._print_body(self.header, self.lines, nlines, cols)
            stdscr.addstr(nlines+2, 0, '')
            stdscr.addstr(' help: ', curses.color_pair(100))
            stdscr.addstr('h')
            stdscr.addstr(' tagging: ', curses.color_pair(100))
            stdscr.addstr(self.current_tag)
            stdscr.addstr(' selected: ', curses.color_pair(100))
            if len(self.selection) == 1:
                stdscr.addstr(self._id_for_index(self.pointer))
            else:
                stdscr.addstr(str(len(self.selection)))
            if cn:
                stdscr.addstr(' key: ', curses.color_pair(100))
                stdscr.addstr(str(cn))
            if stack().canundo():
                stdscr.addstr(' undoable: ', curses.color_pair(100))
                stdscr.addstr(stack().undotext())
            if stack().canredo():
                stdscr.addstr(' redoable: ', curses.color_pair(100))
                stdscr.addstr(stack().redotext())
            _, x = stdscr.getyx()
            stdscr.addstr(' '*(curses.COLS-x-1))
            if self.print_help:
                self._print_help()
            if self.in_dialog:
                self._view_dialoge()
            cn = self.get_key(stdscr)
            if cn == b'q':
                break
            if self.in_dialog:
                self._dialog(cn)
            else:
                self._react(cn, nlines, tabcols)

    _byte_numbers = {str(i).encode() for i in range(10)}
    _control_seq_parts = _byte_numbers.copy()
    _control_seq_parts.add(b';')
    _control_seq_parts.add(b'[')

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
        next_c = get().encode()
        if next_c == b'[':
            # this is a Control Sequence Introducer
            while next_c in self._control_seq_parts:
                cn += next_c
                next_c = get().encode()
        return cn + next_c

    def _print_body(self, header, lines, nlines, cols, y0=0, x0=0):
        padding = ' '*curses.COLS
        h = header + padding
        self.stdscr.addstr(y0, x0, h[cols])
        for i in range(nlines+1):
            pos = i + self.top
            attr = curses.A_REVERSE if self.is_selected(pos) else curses.A_NORMAL
            if pos >= self.total_lines:
                self.stdscr.addstr(y0+i+1, 0, padding)
                continue
            if self.coloring_now in self.df.columns:
                val = self.df[self.coloring_now].iloc[pos]
                if val:
                    col = self.colmap(val)
                    attr |= curses.color_pair(col)
            text = lines[pos]+padding
            self.stdscr.addstr(y0+i+1, x0, text[cols], attr)

    def is_selected(self, pointer):
        return pointer in self.selection

    def _react(self, cn, nlines, tabcols):
        if cn == b'\x01': # CTRL + a
            self.selection = set(range(self.total_lines))
        elif cn == b'h':
            self.toggl_help()
        elif cn == b'f':
            self._dialog_changed = False
            self.in_dialog = True
        elif cn == b'KEY_UP':
            self.pointer -= 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif cn == b'KEY_DOWN':
            self.pointer += 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif cn == b'KEY_SR' or cn == b'\x1b[1;2A':
            self.pointer = max(min(self.selection) - 1, 0)
            self.selection.add(self.pointer)
        elif cn == b'KEY_SF' or cn == b'\x1b[1;2B': # Shift + Down
            self.pointer = min(max(self.selection) + 1, self.total_lines-1)
            self.selection.add(self.pointer)
        elif cn == b'KEY_LEFT':
            if self.lrpos > 0:
                self.lrpos -= 1
        elif cn == b'KEY_SLEFT' or cn == b'\x1b[1;2D':
            self.lrpos = max(0, self.lrpos - int(tabcols/2))
        elif cn == b'KEY_RIGHT':
            self.lrpos += 1
        elif cn == b'KEY_SRIGHT' or cn == b'\x1b[1;2C':
            self.lrpos = self.lrpos + int(tabcols/2)
        elif cn == b'KEY_NPAGE':
            self.top += nlines
            self.pointer = min(self.top, self.total_lines-1)
            self.top = min(self.total_lines-nlines-1, self.top)
            self.selection = {self.pointer}
        elif cn == b'KEY_PPAGE':
            self.top = max(self.top-nlines, 0)
            self.pointer = self.top
            self.selection = {self.pointer}
        elif cn == b'KEY_HOME':
            self.pointer = self.top = 0
            self.selection = {self.pointer}
        elif cn == b'KEY_END':
            self.top = self.total_lines-nlines-1
            self.pointer = self.total_lines-1
            self.selection = {self.pointer}
        elif cn == b'u' and stack().canundo():
            stack().undo()
        elif cn == b'r' and stack().canredo():
            stack().redo()
        else:
            if self.tags[self.current_tag]['type'] is int \
                    and cn in self._byte_numbers:
                # set current tag to value
                self.set_tag(self.current_tag, int(cn), self._view_state)
                return
            for tag, info in self.tags.items():
                if cn == info['key']:
                    if info['type'] is int:
                        logging.info(f'Starting to tag {tag}.')
                        self.current_tag = tag
                    elif info['type'] is str:
                        logging.info(f'Starting make a {tag}.')
                        self.make_str(tag)

    def make_str(self, tag):
        hight = min(23, curses.LINES-4)
        width = min(80, curses.COLS-4)
        editwin = curses.newwin(hight-3, width-3, 3, 3)
        rectangle(self.stdscr, 2, 2, hight, width)
        ids = self._id_for_index(list(self.selection))
        if len(ids)>1:
            id = f'[{ids[0]} ...]'
        else:
            id = ids[0]
        text = f"Enter {tag} for {id}: (hit Ctrl-G to send)"
        self.stdscr.addstr(2, 4, text[:(width-4)])
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
        box.edit()
        message = box.gather().strip()
        if message != current_text:
            self.set_tag(tag, message, self._view_state)

    def _id_for_index(self, index):
        return self.df["id"].iloc[index]

    view_attributes = {
        'selection',
        'pointer',
        'top',
        'filter',
        'sort_columns',
        'ordered_columns',
        'color_by'
    }

    @property
    def _view_state(self):
        return {attr: getattr(self, attr) for attr in self.view_attributes}

    @_view_state.setter
    def _view_state(self, new_state):
        for critical in ['filter', 'sort_columns', 'color_by']:
            if new_state[critical] is not getattr(self, critical):
                self._update_now = True
        for key, value in new_state.items():
            setattr(self, key, value)

    def get_current_values(self, tag):
        selection = list(self.selection)
        ids = self._id_for_index(selection)
        td = self.tag_data[tag]
        return {td[id] for id in ids if id in td}

    @undoable
    def set_tag(self, tag, val, view_state):
        self._view_state = view_state
        lselected = list(self.selection)
        ids = self._id_for_index(lselected)
        td = self.tag_data[tag]
        current =  {id:td.get(id) for id in ids}
        if self.tags[tag]['type'] is str:
            log_val = val.splitlines()[0]
            if len(log_val) > 20:
                log_val = log_val[:17]+'...'
        else:
            log_val = val
        if len(ids) == 1:
            id = next(iter(ids))
            short_desc = long_desc = f'setting tag "{tag}" to '\
                                     f'"{log_val}" for {id}'
            short_desc = f'{tag}={log_val} for {id}'
        else:
            lids = list(ids)
            long_desc = f'setting tag "{tag}" to "{log_val}" for {lids}'
            short_desc = f'{tag}={log_val} for [{lids[0]}, ...]'
        logging.info(long_desc)
        for id, index in zip(ids, lselected):
            td[id] = val
            self.df.loc[self.df.index[index], tag] = val
        self.save_tag_data()
        self.stale_lines.update(self.selection)
        yield short_desc
        logging.info('undoing '+long_desc)
        for ind, (id, v) in enumerate(current.items()):
            if v is None or np.isnan(v):
                del td[id]
                self.df.loc[self.df.index[lselected[ind]], tag] = '-'
            else:
                td[id] = v
                self.df.loc[self.df.index[lselected[ind]], tag] = v
        self.save_tag_data()
        self.stale_lines.update(view_state['selection'])
        self._view_state = view_state

    def save_tag_data(self):
        last_pid = self.last_saver_pid
        self.last_saver_pid = os.fork()
        if self.last_saver_pid == 0:
            if last_pid is not None:
                try:
                    os.waitpid(last_pid, 0)
                except ChildProcessError:
                    pass
            try:
                with open(self.output, 'w') as f:
                    f.write(yaml.dump(self.tag_data))
            except:
                os._exit(1)
            os._exit(0)

    def _print_help(self):
        help = self.helptext
        hight = min(len(help)+1, curses.LINES-4)
        width = min(80, curses.COLS-4)
        self.win = self.stdscr.subwin(hight, width, 2, 2)
        self.win.clear()
        self.win.border()
        for i in range(1, hight-1):
            self.win.addstr(i, 5, help[i].strip()[:width-6])
        if hight-1 < len(help):
            self.win.addstr(i, 1, ' '*(width-2))
            self.win.addstr(i, 5, '...'[:width-6])

    _window_width = 120

    def _view_dialoge(self):
        self.table_y0 = 5
        self.table_x0 = 6
        hight = min(len(self.ordered_columns)+self.table_y0+2, curses.LINES-4)
        width = min(self._window_width, curses.COLS-4)
        self.win = self.stdscr.subwin(hight, width, 2, 2)
        self.win.clear()
        self.win.border()
        buttons = {
            'e':'exit',
            'Enter':'edit regex',
            'r':'reset',
            'd':'toggle deactivate',
            's':'toggle sort by',
            'c':'toggle color by',
            'shift+up/down':'change order'
        }
        self.win.move(1, self.table_x0-2)
        for key, desc in buttons.items():
            hintlen = len(key)+len(desc)+4
            _, x = self.win.getyx()
            if x+hintlen > width-2:
                break
            self.win.addstr('  ')
            self.win.addstr(key+':', curses.color_pair(100))
            self.win.addstr(' '+desc)
        legend = {
            'legend:':103,
            'deactivated':102,
            'sorted by':101,
            'color by':104
        }
        self.win.move(2, self.table_x0-2)
        for lable, col in legend.items():
            hintlen = len(lable)+2
            _, x = self.win.getyx()
            if x+hintlen > width-2:
                break
            self.win.addstr('  ')
            self.win.addstr(lable, curses.color_pair(col))
        self.indentation = max(len(c) for c in self.ordered_columns)
        #self.win.addstr(2, 1, f'self.woffset: {self.woffset} hight:{hight}')
        self.win.addstr(4, self.table_x0,
                        'column' + ' '*(self.indentation-5) + 'regex')
        self.woffset = max(0, self.col_pointer-hight+self.table_y0+3)
        for i, col in enumerate(self.ordered_columns):
            if i < self.woffset:
                continue
            elif self.woffset > 0 and i == self.woffset:
                self.win.addstr(self.table_y0, self.table_x0, '...'[:width-6])
                continue
            ypos = i+self.table_y0-self.woffset
            if ypos+2 == hight:
                self.win.addstr(ypos, self.table_x0, '...'[:width-6])
                break
            attr = curses.A_REVERSE if i==self.col_pointer else curses.A_NORMAL
            if col not in self.show_columns:
                attr |= curses.color_pair(legend['deactivated'])
            elif col == self.color_by:
                attr |= curses.color_pair(legend['color by'])
            elif col in self.sort_columns:
                attr |= curses.color_pair(legend['sorted by'])
            filter = self.filter.get(col, '*')
            text = col + ' '*(self.indentation-len(col)+1) + filter
            self.win.addstr(ypos, self.table_x0, text[:width-6], attr)
            if col in self.tag_data:
                self.win.addstr(ypos, 2, 'tag')

    def _dialog(self, cn):
        if cn == b'e':
            self.in_dialog = False
            if self._dialog_changed:
                self._update_now = True
        elif cn == b'KEY_ENTER' or cn == b'^J':
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
                logging.info(f'Setting filter for "{col}": "{filter}"')
                self.filter[col] = filter
            else:
                logging.info(f'Setting empty filter for "{col}".')
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
            logging.info(f'Resetting filter for "{col}".')
            if col in self.filter:
                self.filter.pop(col, None)
                self._dialog_changed = True
        elif cn == b'd':
            col = self.ordered_columns[self.col_pointer]
            if col == 'id':
                logging.debug(f'Cannot deactivate "{col}".')
            elif col in self.show_columns:
                logging.info(f'Deactivate "{col}".')
                self.show_columns.remove(col)
            else:
                logging.info(f'Activate "{col}".')
                self.show_columns.add(col)
            self._dialog_changed = True
        elif cn == b's':
            col = self.ordered_columns[self.col_pointer]
            if col in self.sort_columns:
                logging.info(f'Do not sort by "{col}".')
                self.sort_columns.remove(col)
            else:
                logging.info(f'Sort by "{col}".')
                self.sort_columns.add(col)
            self._dialog_changed = True
        elif cn == b'KEY_SR' or cn == b'\x1b[1;2A':
            col_val = self.ordered_columns[self.col_pointer]
            logging.info(f'Moving column "{col_val}" up.')
            col_pos = self.col_pointer
            self.col_pointer -= 1
            if self.col_pointer < 0:
                self.col_pointer = len(self.ordered_columns)-1
                self.ordered_columns.remove(col_val)
                self.ordered_columns.append(col_val)
            else:
                self.ordered_columns[col_pos] = \
                        self.ordered_columns[self.col_pointer]
                self.ordered_columns[self.col_pointer] = col_val
                self._dialog_changed = True
        elif cn == b'KEY_SR' or cn == b'\x1b[1;2B':
            col_val = self.ordered_columns[self.col_pointer]
            logging.info(f'Moving column "{col_val}" down.')
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
            logging.info(f'Coloring by "{col}".')
            if self.color_by == col:
                self.color_by = False
            else:
                self.color_by = col
            self._dialog_changed = True

    _helptext = """
        h           Show/hide help window.
        q           Save and quit geotag.
        f           Filter dialoge.
        Up          Move upward.
        Down        Move downward.
        Pageup      Move upward one page.
        Pagedown    Move down one page.
        Shift+Up    Select upward.
        Shift+Down  Select downward.
        Left        Move to the left hand side.
        Right       Move to the right hand side.
        Shift+Left  Move to the left by half a page.
        Shift+Right Move to the right by half a page.
        Home        Move to the start of the table.
        End         Move to the end of the table.
        Ctrl+a      Select all.
        """.splitlines()

    @property
    def helptext(self):
        h = self._helptext[:]
        indent = 12
        for tag, info in self.tags.items():
            keys = '+'.join(keypartmap(c) for c in info['key'])
            space = ' '*max(1, indent-len(keys))
            if info['type'] is str:
                h.append(keys+space+'Make a '+tag+'.')
            else:
                h.append(keys+space+'Start tagging '+tag+'.')
        return h

if __name__ == "__main__":
    main()
