import curses
curses.wrapper(lambda sc: sc.get_wch())
