import os
import argparse
import pandas as pd
import curses
from curses.textpad import Textbox, rectangle
import time
import locale

# use system default localization
locale.setlocale(locale.LC_ALL, 'C')
code = locale.getpreferredencoding()

def main():
    desc = 'Interface to quickly tag geo data sets.'
    parser = argparse.ArgumentParser(description=desc)
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
    args = parser.parse_args()
    app = App(args)
    curses.wrapper(app.run)

tcolors = [196, 203, 202, 208, 178, 148, 106, 71, 31, 26]

class App:
    def __init__(self, args):
        self.df = pd.read_csv(args.rnaSeq, sep = "\t", low_memory=False)
        self.sort_columns = list()
        self.reset_selected_cols()
        self.toggl_help(False)
        self.in_dialog = False
        self.pointer = 0
        self.col_pointer = 0
        self.selection = {self.pointer}
        self.lrpos = 0
        self.top = 0
        self.update_current()

    def reset_selected_cols(self):
        self.colnames = ['gse', 'id', 'status', 'coarse.cell.type',
                         'pattern', 'val']

    def toggl_help(self, to: bool=None):
        if to is not None:
            self.print_help = to
        else:
            self.print_help = not self.print_help

    def update_current(self):
        r = self.df.copy()
        if self.sort_columns:
            r = r.sort_values(self.sort_columns)
        r = r.loc[:, self.colnames]
        self.current = r

    def header_body(self):
        df = self.current
        lines = df.to_string(index=False).splitlines()
        header = lines[0]
        lines = lines[1:]
        self.total_lines = len(lines)
        return header, lines, self.total_lines, df

    def _init_curses(self):
        curses.use_default_colors()
        curses.init_pair(100, curses.COLOR_GREEN, -1)
        curses.init_pair(101, curses.COLOR_BLUE, -1)
        curses.init_pair(102, curses.COLOR_RED, -1)
        curses.init_pair(103, curses.COLOR_WHITE, -1)
        for i, col in enumerate(tcolors):
            curses.init_pair(i+1, col, -1)

    def run(self, stdscr):
        self._init_curses()
        self.stdscr = stdscr
        message = ''
        c = 0
        cn = b''
        header, lines, self.total_lines, df = self.header_body()
        while True:
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
                          f'pointer: {self.pointer}' + padding)
            cn = curses.keyname(c)
            stdscr.addstr(nlines+3, 0, '%s is %s and %s' %
                          (cn, c, b'^' in cn) + padding)
            #stdscr.addstr(nlines+4, 0, '%s %s' % (curr['id'].iloc[self.pointer], ' '*curses.COLS))
            if len(self.selection) == 1:
                stdscr.addstr(nlines+4, 0,
                              f'selected: {df["id"].iloc[self.pointer]}'
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
            if pos > self.total_lines:
                break
            col = curses.color_pair(i%len(tcolors)+1)
            attr = curses.A_REVERSE if self.is_selected(pos) else curses.A_NORMAL
            text = lines[pos]+padding
            self.stdscr.addstr(y0+i+1, x0, text[cols], col | attr)

    def is_selected(self, pointer):
        return pointer in self.selection

    def _react(self, c, nlines, tabcols):
        cn = curses.keyname(c)
        if b'^' in cn: # CTRL Key
            if cn == b'^J': # ENTER
                pass
            elif cn == b'^A':
                self.selection = set(range(self.total_lines))
        elif c == ord('c'):
            curses.echo()
            s = self.stdscr.getstr(0,0, 15)
            curses.noecho()
        elif c == ord('h'):
            self.toggl_help()
        elif c == ord('v'):
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
            self.lrpos = max(0, self.lrpos - tabcols)
        elif c == curses.KEY_RIGHT:
            self.lrpos += 1
        elif c == curses.KEY_SRIGHT or cn == b'C':
            self.lrpos = self.lrpos + tabcols
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
        win = self.stdscr.subwin(hight, width, 2, 2)
        win.clear()
        win.border()
        for i in range(1, hight-1):
            win.addstr(i, 5, self.helptext[i].strip()[:width-6])
        if hight < len(self.helptext):
            win.addstr(i, 1, ' '*(width-2))
            win.addstr(i, 5, '...'[:width-6])

    def _view_dialoge(self):
        hight = min(len(self.df.columns)+5, curses.LINES-4)
        width = min(80, curses.COLS-4)
        win = self.stdscr.subwin(hight, width, 2, 2)
        win.clear()
        win.border()
        htext = 'c: clear  d: toggle deactivate  Enter: edit  Esc: exit'
        buttons = {
            'c':'clear',
            'd':'toggle deactivate',
            'Enter':'edit',
            'Esc':'exit'
        }
        win.move(1, 5)
        for key, desc in buttons.items():
            hintlen = len(key)+len(desc)+4
            _, x = win.getyx()
            if x+hintlen > width-2:
                break
            win.addstr('  ')
            win.addstr(key+':', curses.color_pair(100))
            win.addstr(' '+desc)
        legend = {
            'legend:':103,
            'deactivated':102,
            'sorted by':101
        }
        win.move(2, 5)
        for lable, col in legend.items():
            hintlen = len(lable)+2
            _, x = win.getyx()
            if x+hintlen > width-2:
                break
            win.addstr('  ')
            win.addstr(lable, curses.color_pair(col))
        indentation = max(len(c) for c in self.df.columns)
        offset = max(0, self.col_pointer-hight+6)
        #win.addstr(2, 1, f'offset: {offset} hight:{hight}')
        for i, col in enumerate(self.df.columns):
            if i < offset:
                continue
            elif offset > 0 and i == offset:
                win.addstr(3, 5, '...'[:width-6])
                continue
            ypos = i+3-offset
            if ypos+2 == hight:
                win.addstr(ypos, 5, '...'[:width-6])
                break
            attr = curses.A_REVERSE if i==self.col_pointer else curses.A_NORMAL
            if col in self.sort_columns:
                attr |= curses.color_pair(legend['sorted by'])
            elif col not in self.colnames:
                attr |= curses.color_pair(legend['deactivated'])
            text = col + ' '*(indentation-len(col)+1) + f'text {i}'
            win.addstr(ypos, 5, text[:width-6], attr)

    def _dialog(self, c):
        cn = curses.keyname(c)
        if cn == b'^[':
            self.in_dialog = False
        elif c == curses.KEY_UP:
            self.col_pointer -= 1
            self.col_pointer %= len(self.df.columns)
        elif c == curses.KEY_DOWN:
            self.col_pointer += 1
            self.col_pointer %= len(self.df.columns)

    helptext = """
        h           This help window.
        q           Save and quit geotag.
        v           View dialoge.
        Up          Move upward.
        Down        Move downward.
        Pageup      Move upward one page.
        Pagedown    Move down one page.
        Shift+Up    Select upward.
        Shift+Down  Select downward.
        Left        Move to the left hand side.
        Right       Move to the right hand side.
        Shift+Left  Move to the left by one page.
        Shift+Right Move to the right by one page.
        Home        Move to the start of the table.
        End         Move to the end of the table.

        Ctrl+a      Select all.
        """.splitlines()

if __name__ == "__main__":
    main()
