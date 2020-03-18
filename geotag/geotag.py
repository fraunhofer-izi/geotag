import os
import argparse
import pandas as pd
import curses
from curses.textpad import Textbox, rectangle
import time
import locale

# init curses
#locale.setlocale(locale.LC_ALL, '')
#code = locale.getpreferredencoding()

def main():
    desc = 'Interface to quickly tag geo data sets.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--rnaSeq',
                        help='.RDS table containing the extraction status of '
                        'RNASeq studies.', type=str, metavar='path',
                        default='/mnt/ribolution/user_worktmp/dominik.otto/'
                        'tumor-deconvolution-dream-challenge/'
                        'extraction_stats_head.tsv')
    parser.add_argument('--array',
                        help='.RDS table containing the extraction status of '
                        'microarray studies.', type=str, metavar='path',
                        default='/mnt/ribolution/user_worktmp/dominik.otto/'
                        'tumor-deconvolution-dream-challenge/'
                        'extraction_stats_array.tsv')
    args = parser.parse_args()
    app = App(args)
    curses.wrapper(app.run)

class App:
    def __init__(self, args):
        self.rnaseq = pd.read_csv(args.rnaSeq, sep = "\t", low_memory=False)
        self.show_now = 'selected_cols'
        self.reset_selected_cols()
        self.toggl_help(False)
        self.pointer = 0
        self.selection = {self.pointer}
        self.lrpos = 0
        self.top = 0

    def reset_selected_cols(self):
        self.colnames = ['gse', 'id', 'status', 'coarse.cell.type',
                         'pattern', 'val']

    def toggl_help(self, to: bool=None):
        if to is not None:
            self.print_help = to
        else:
            self.print_help = not self.print_help

    @property
    def current(self):
        if self.show_now == 'raw':
            return self.rnaseq
        elif self.show_now == 'selected_cols':
            return self.rnaseq.loc[:, self.colnames]

    def header_body(self):
        df = self.current
        lines = df.to_string(index=False).splitlines()
        header = lines[0]
        lines = lines[1:]
        self.total_lines = len(lines)
        return header, lines, self.total_lines, df

    def _init_curses(self):
        curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE)

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
            self.top = self.pointer - nlines if self.pointer >= self.top + nlines else self.top
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
                              f'selected: {len(self.selection)}' + ' '*curses.COLS)
            if self.print_help:
                self._print_help()
            c = stdscr.getch()
            if c == ord('q'):
                break
            self._react(c, nlines, tabcols)

    def _print_body(self, header, lines, nlines, cols, y0=0, x0=0):
        padding = ' '*curses.COLS
        h = header + padding
        self.stdscr.addstr(y0, x0, h[cols])
        for i in range(nlines+1):
            pos = i + self.top
            if pos > self.total_lines:
                break
            attr = curses.A_REVERSE if self.is_selected(pos) else curses.A_NORMAL
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
                self.selection = range(self.total_lines)
        elif c == ord('c'):
            curses.echo()
            s = self.stdscr.getstr(0,0, 15)
            curses.noecho()
        elif c == ord('h'):
            self.toggl_help()
        elif c == ord('v'):
            self._view_dialoge()
        elif c == curses.KEY_UP:
            self.pointer -= 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif c == curses.KEY_DOWN:
            self.pointer += 1
            self.pointer %= self.total_lines
            self.selection = {self.pointer}
        elif cn == b'A': # Shift + Up
            self.pointer = max(min(self.selection) - 1, 0)
            self.pointer %= self.total_lines
            self.selection.add(self.pointer)
        elif cn == b'B': # Shift + Down
            self.pointer = min(max(self.selection) + 1, self.total_lines)
            self.pointer %= self.total_lines
            self.selection.add(self.pointer)
        elif c == curses.KEY_LEFT:
            if self.lrpos > 0:
                self.lrpos -= 1
        elif cn == b'D': # Shift + Left
            self.lrpos = max(0, self.lrpos - tabcols)
        elif c == curses.KEY_RIGHT:
            self.lrpos += 1
        elif cn == b'C': # Shift + Right
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
            text = '    ' + self.helptext[i].strip()
            win.addstr(i, 1, text[:width-2])
        if hight < len(self.helptext):
            win.addstr(i, 1, ' '*(width-2))
            win.addstr(i, 1, '    ...'[:width-2])
        self.stdscr.refresh()

    def _view_dialoge(self):
        pass

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
