import os
import argparse
import pandas as pd
import curses
from curses.textpad import Textbox, rectangle
import time
import locale
locale.setlocale(locale.LC_ALL, '')
code = locale.getpreferredencoding()

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
    if False:
        rnaseq = pd.read_csv(args.rnaSeq, sep = "\t", low_memory=False)\
            .set_index('id')
        lines = rnaseq.to_string().splitlines()
        for i, line in enumerate(lines):
            print(line[0:10])
        time.sleep(1)
    curses.wrapper(application, args)
    print('I am the main.')

def application(stdscr, args):
    stdscr.clear()

    rnaseq = pd.read_csv(args.rnaSeq, sep = "\t", low_memory=False)
    curr = rnaseq.copy()
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_WHITE)
    lines = curr.to_string().splitlines()
    header = lines[0]
    lines = lines[1:]
    total_lines = len(lines)

    message = ''
    pointer = 0
    lrpos = 0
    top = 0
    selection = {pointer}
    c = cn = ''
    while True:
        curses.update_lines_cols()
        nlines = curses.LINES-6
        top = pointer if pointer < top else top
        top = pointer - nlines if pointer >= top + nlines else top
        tabcols = curses.COLS
        cols = slice(lrpos, lrpos+tabcols)
        button = top + nlines
        stdscr.addstr(0, 0, header[cols])
        for i in range(nlines+1):
            pos = i + top
            if pos > total_lines:
                break
            attr = curses.A_REVERSE if pos in selection else curses.A_NORMAL
            stdscr.addstr(i+1, 0, lines[pos][cols], attr)
        stdscr.addstr(nlines+2, 0, f'top: {top} '
                      f'nlines: {nlines} '
                      f'total_lines: {total_lines} '
                      f'pointer: {pointer} ' +
                      ' '*curses.COLS)
        stdscr.addstr(nlines+3, 0, '%s is %s %s' % (cn, c, ' '*curses.COLS))
        stdscr.addstr(nlines+4, 0, '%s %s' % (curr['id'].iloc[pointer], ' '*curses.COLS))
        c = stdscr.getch()
        cn = curses.keyname(c)
        if c == ord('q'):
            break
        elif c == ord('c'):
            curses.echo()
            s = stdscr.getstr(0,0, 15)
            curses.noecho()
        elif c == curses.KEY_UP:
            pointer -= 1
            pointer %= total_lines
            selection = {pointer}
        elif c == curses.KEY_DOWN:
            pointer += 1
            pointer %= total_lines
            selection = {pointer}
        elif cn == b'A': # SHIFT + UP
            pointer = max(min(selection) - 1, 0)
            pointer %= total_lines
            selection.add(pointer)
        elif cn == b'B': # SHIFT + DOWN
            pointer = min(max(selection) + 1, total_lines)
            pointer %= total_lines
            selection.add(pointer)
        elif c == curses.KEY_LEFT:
            if lrpos > 0:
                lrpos -= 1
        elif cn == b'D': # SHIFT + LEFT
            lrpos = max(0, lrpos - tabcols)
        elif c == curses.KEY_RIGHT:
            lrpos += 1
        elif cn == b'C': # SHIFT + RIGHT
            lrpos = lrpos + tabcols
        elif c == curses.KEY_NPAGE:
            top += nlines
            pointer = min(top, total_lines-1)
            top = min(total_lines-nlines-1, top)
            selection = {pointer}
        elif c == curses.KEY_PPAGE:
            top = max(top-nlines, 0)
            pointer = top
            selection = {pointer}
        elif c == ord('n'):
            stdscr.addstr(0, 0, "Enter IM message: (hit Ctrl-G to send)")
            editwin = curses.newwin(5,30, 2,1)
            rectangle(stdscr, 1,0, 1+5+1, 1+30+1)
            stdscr.refresh()
            box = Textbox(editwin)
            # Let the user edit until Ctrl-G is struck.
            box.edit()
            # Get resulting contents
            message = box.gather()
    #pad.addstr(0, 0, 'hello')
    #pad.addstr(10, 0, 'hello', curses.color_pair(1))
    #pad.refresh(0,0,0,0,100,100)
    #stdscr.refresh()

if __name__ == "__main__":
    main()
