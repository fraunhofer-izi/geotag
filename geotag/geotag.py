import os
import argparse
import pandas as pd
import curses
from curses.textpad import Textbox, rectangle
import time
import locale
import logging
import yaml

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
                        "geotag/data/extraction_stats_head.tsv")
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
                        action="store_true",
                        type=str, metavar='bool')
    args = parser.parse_args()
    if if not args.update and os.path.exists(args.state):
        app = pickle.load(open(args.state, 'r'))
        if app.__version__ != App.__version__:
            raise Exeption(f'The geotag version "{App.__version__}" differs '
                    'from version of the cache "{app.__version__}". '
                    'Pass the parameter --update if you want to overwrite it.')
        # transfer attributes
    else:
        app = App(**vars(args))
    curses.wrapper(app.run)

tcolors = [196, 203, 202, 208, 178, 148, 106, 71, 31, 26]
default_tags = {
    'quality':{
        'type':int,
        'desc':'From 0 to 9.',
        'key':b'^q'
    },
    'note':{
        'type':str,
        'desc':'A note.',
        'key':b'^n'
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
    __version__ = '0.0.1'

    def __init__(self, rnaSeq, array, log, tags, output, **kwargs):
        logging.basicConfig(filename=log, filemode='a', level=logging.DEBUG,
                format='[%(asctime)s] %(levelname)s: %(message)s')
        self.raw_df = pd.read_csv(rnaSeq, sep = "\t", low_memory=False)
        self.raw_df.index = uniquify(self.raw_df['id'])
        self.sort_columns = set()
        self.filter = dict()
        self.toggl_help(False)
        self.in_dialog = False
        self.pointer = 0
        self.col_pointer = 0
        self.selection = {self.pointer}
        self.lrpos = 0
        self.top = 0
        self.color_by = False
        if not os.path.exists(tags):
            logging.warning(f'The tags file "{tags}" dose not exist. '
                           'Using default tags...')
            self.tags = default_tags
        else:
            self.tags = yaml.load(tags)
        if not os.path.exists(output):
            logging.warning(f'The output file "{output}" dose not exist yet. '
                           'Starting over...')
            self.tag_data = dict()
        else:
            self.tag_data = yaml.load(output)
        for tag in self.tags:
            self.tag_data.setdefault(tag, dict())
        self.reset_cols()

    def reset_cols(self):
        self.ordered_columns = [
            'id',
            'quality',
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
            tagd = pd.DataFrame.from_dict(tags, orient='index', columns=[col])
            data_frames.append(tagd)
        r = pd.concat(data_frames, axis=1, join='outer')
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
        if pd.api.types.is_numeric_dtype(r[self.color_by].dtype):
            self.colmap = lambda x: int(x%10)+1
        else:
            cmap = {key:i%10+1 for i, key in
                    enumerate(sorted(set(r[self.color_by])))}
            self.colmap = lambda x: cmap[x]

    def header_body(self):
        self.update_df()
        lines = self.df.to_string(index=False).splitlines()
        header = lines[0]
        lines = lines[1:]
        self.total_lines = len(lines)
        return header, lines, self.total_lines

    def _init_curses(self):
        curses.use_default_colors()
        curses.init_pair(100, curses.COLOR_GREEN, -1)
        curses.init_pair(101, curses.COLOR_BLUE, -1)
        curses.init_pair(102, curses.COLOR_RED, -1)
        curses.init_pair(103, curses.COLOR_WHITE, -1)
        curses.init_pair(104, curses.COLOR_YELLOW, -1)
        for i, col in enumerate(tcolors):
            curses.init_pair(i+1, col, -1)

    def run(self, stdscr):
        self._init_curses()
        self.stdscr = stdscr
        message = ''
        c = 0
        cn = b''
        self._update_now = True
        while True:
            if self._update_now:
                header, lines, self.total_lines = self.header_body()
                self._update_now = False
            curses.update_lines_cols()
            padding = ' '*curses.COLS
            nlines = curses.LINES-6
            self.top = self.pointer if self.pointer < self.top else self.top
            self.top = self.pointer - nlines \
                    if self.pointer >= self.top + nlines else self.top
            tabcols = curses.COLS
            cols = slice(self.lrpos, self.lrpos+tabcols)
            button = self.top + nlines
            self._print_body(header, lines, nlines, cols)
            stdscr.addstr(nlines+2, 0, f'top: {self.top} '
                          f'nlines: {nlines} '
                          f'total_lines: {self.total_lines} '
                          f'pint_help: {self.print_help} '
                          f'pointer: {self.pointer} '
                          f'color by: {self.coloring_now}' + padding)
            cn = curses.keyname(c)
            stdscr.addstr(nlines+3, 0, '%s is %s and %s' %
                          (cn, c, b'^' in cn) + padding)
            #stdscr.addstr(nlines+4, 0, '%s %s' % (curr['id'].iloc[self.pointer], ' '*curses.COLS))
            if len(self.selection) == 1:
                stdscr.addstr(nlines+4, 0,
                              f'selected: {self.df["id"].iloc[self.pointer]}'
                              + padding)
            else:
                stdscr.addstr(nlines+4, 0,
                              f'selected: {len(self.selection)}'
                              + ' '*curses.COLS)
            if self.print_help:
                self._print_help()
            if self.in_dialog:
                self._view_dialoge()
            c = stdscr.getch()
            if c == ord('q'):
                break
            if self.in_dialog:
                self._dialog(c)
            else:
                self._react(c, nlines, tabcols)

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

    def _react(self, c, nlines, tabcols):
        cn = curses.keyname(c)
        if b'^' in cn: # CTRL Key
            if cn == b'^J': # ENTER
                pass
            elif cn == b'^A':
                self.selection = set(range(self.total_lines))
        elif c == ord('h'):
            self.toggl_help()
        elif c == ord('f'):
            self._dialog_changed = False
            self.in_dialog = True
        elif c == curses.KEY_UP:
            self.pointer -= 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif c == curses.KEY_DOWN:
            self.pointer += 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif c == curses.KEY_SR or cn == b'A':
            self.pointer = max(min(self.selection) - 1, 0)
            self.selection.add(self.pointer)
        elif c == curses.KEY_SF or cn == b'B': # Shift + Down
            self.pointer = min(max(self.selection) + 1, self.total_lines-1)
            self.selection.add(self.pointer)
        elif c == curses.KEY_LEFT:
            if self.lrpos > 0:
                self.lrpos -= 1
        elif c == curses.KEY_SLEFT or cn == b'D':
            self.lrpos = max(0, self.lrpos - int(tabcols/2))
        elif c == curses.KEY_RIGHT:
            self.lrpos += 1
        elif c == curses.KEY_SRIGHT or cn == b'C':
            self.lrpos = self.lrpos + int(tabcols/2)
        elif c == curses.KEY_NPAGE:
            self.top += nlines
            self.pointer = min(self.top, self.total_lines-1)
            self.top = min(self.total_lines-nlines-1, self.top)
            self.selection = {self.pointer}
        elif c == curses.KEY_PPAGE:
            self.top = max(self.top-nlines, 0)
            self.pointer = self.top
            self.selection = {self.pointer}
        elif c == curses.KEY_HOME:
            self.pointer = self.top = 0
            self.selection = {self.pointer}
        elif c == curses.KEY_END:
            self.top = self.total_lines-nlines-1
            self.pointer = self.total_lines-1
            self.selection = {self.pointer}
        elif c == ord('n'):
            self.stdscr.addstr(0, 0, "Enter IM message: (hit Ctrl-G to send)")
            editwin = curses.newwin(5,30, 2,1)
            rectangle(self.stdscr, 1,0, 1+5+1, 1+30+1)
            self.stdscr.refresh()
            box = Textbox(editwin)
            # Let the user edit until Ctrl-G is struck.
            box.edit()
            # Get resulting contents
            message = box.gather()

    def _print_help(self):
        hight = min(len(self.helptext), curses.LINES-4)
        width = min(80, curses.COLS-4)
        self.win = self.stdscr.subwin(hight, width, 2, 2)
        self.win.clear()
        self.win.border()
        for i in range(1, hight-1):
            self.win.addstr(i, 5, self.helptext[i].strip()[:width-6])
        if hight < len(self.helptext):
            self.win.addstr(i, 1, ' '*(width-2))
            self.win.addstr(i, 5, '...'[:width-6])

    _window_width = 120

    def _view_dialoge(self):
        table_y0 = 5
        x0 = 6
        hight = min(len(self.ordered_columns)+table_y0+2, curses.LINES-4)
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
        self.win.move(1, x0-2)
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
        self.win.move(2, x0-2)
        for lable, col in legend.items():
            hintlen = len(lable)+2
            _, x = self.win.getyx()
            if x+hintlen > width-2:
                break
            self.win.addstr('  ')
            self.win.addstr(lable, curses.color_pair(col))
        self.indentation = max(len(c) for c in self.ordered_columns)
        #self.win.addstr(2, 1, f'self.woffset: {self.woffset} hight:{hight}')
        self.win.addstr(4, x0, 'column' + ' '*(self.indentation-5) + 'regex')
        self.woffset = max(0, self.col_pointer-hight+table_y0+3)
        for i, col in enumerate(self.ordered_columns):
            if i < self.woffset:
                continue
            elif self.woffset > 0 and i == self.woffset:
                self.win.addstr(table_y0, x0, '...'[:width-6])
                continue
            ypos = i+table_y0-self.woffset
            if ypos+2 == hight:
                self.win.addstr(ypos, x0, '...'[:width-6])
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
            self.win.addstr(ypos, x0, text[:width-6], attr)
            if col in self.tag_data:
                self.win.addstr(ypos, 2, 'tag')

    def _dialog(self, c):
        cn = curses.keyname(c)
        if c == ord('e'):
            self.in_dialog = False
            if self._dialog_changed:
                self._update_now = True
        elif c == curses.KEY_ENTER or cn == b'^J':
            col = self.ordered_columns[self.col_pointer]
            ypos = self.col_pointer + 6 - self.woffset
            xpos = self.indentation + 8
            width = self._window_width - xpos
            editwin = self.stdscr.subwin(1, width, ypos, xpos)
            editwin.addstr(0, 0, self.filter.get(col, ''))
            self.stdscr.refresh()
            box = curses.textpad.Textbox(editwin)
            box.edit()
            filter = box.gather().strip()
            if filter not in ['*', '']:
                logging.info(f'Setting filter for "{col}": "{filter}"')
                self.filter[col] = filter
            else:
                logging.info(f'Setting empty filter for "{col}".')
                self.filter.pop(col, None)
            self._dialog_changed = True
        elif c == curses.KEY_UP:
            self.col_pointer -= 1
            self.col_pointer %= len(self.ordered_columns)
        elif c == curses.KEY_DOWN:
            self.col_pointer += 1
            self.col_pointer %= len(self.ordered_columns)
        elif c == ord('r'):
            col = self.ordered_columns[self.col_pointer]
            logging.info(f'Resetting filter for "{col}".')
            if col in self.filter:
                self.filter.pop(col, None)
                self._dialog_changed = True
        elif c == ord('d'):
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
        elif c == ord('s'):
            col = self.ordered_columns[self.col_pointer]
            if col in self.sort_columns:
                logging.info(f'Do not sort by "{col}".')
                self.sort_columns.remove(col)
            else:
                logging.info(f'Sort by "{col}".')
                self.sort_columns.add(col)
            self._dialog_changed = True
        elif c == curses.KEY_SR or cn == b'A':
            col_val = self.ordered_columns[self.col_pointer]
            logging.info(f'Moving column "{col_val}" up.')
            col_pos = self.col_pointer
            self.col_pointer -= 1
            self.col_pointer %= len(self.ordered_columns)
            self.ordered_columns[col_pos] = \
                    self.ordered_columns[self.col_pointer]
            self.ordered_columns[self.col_pointer] = col_val
            self._dialog_changed = True
        elif c == curses.KEY_SF or cn == b'B': # Shift + Down
            col_val = self.ordered_columns[self.col_pointer]
            logging.info(f'Moving column "{col_val}" down.')
            col_pos = self.col_pointer
            self.col_pointer += 1
            self.col_pointer %= len(self.ordered_columns)
            self.ordered_columns[col_pos] = \
                    self.ordered_columns[self.col_pointer]
            self.ordered_columns[self.col_pointer] = col_val
            self._dialog_changed = True
        elif c == ord('c'):
            col = self.ordered_columns[self.col_pointer]
            logging.info(f'Coloring by "{col}".')
            if self.color_by == col:
                self.color_by = False
            else:
                self.color_by = col
            self._dialog_changed = True

    helptext = """
        h           This help window.
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

if __name__ == "__main__":
    main()
