#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module allowing for ``python -m geotag ...``."""
import argparse
import os
import errno
import pickle
import curses
from .geotag import App

def main():
    desc = 'Interface to quickly tag geo data sets. Set a user through ' \
           'the environemnt varoable USER.'
    parser = argparse.ArgumentParser(description=desc,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--table',
                        help='One or multiple tsv table containing the '
                        'samples line-wise and at least the columns '
                        '`gse` and `id`.',
                        nargs='+', metavar='path.tsv')
    parser.add_argument('--log',
                        help='The file path for the log.',
                        type=str, metavar='path',
                        default=f"{os.environ['HOME']}/geotag/"
                                f"{os.environ['USER']}.log")
    parser.add_argument('--tags',
                        help='The file path for the tag yaml.',
                        type=str, metavar='path.yml',
                        default=f"{os.environ['HOME']}/geotag/"
                                "tags.yml")
    parser.add_argument('--output',
                        help='The output file path.',
                        type=str, metavar='path.yml',
                        default=f"{os.environ['HOME']}/geotag/"
                                f"{os.environ['USER']}.yml")
    parser.add_argument('--softPath',
                        help='Path to the soft file directory s.t. '
                        'file paths are path/GSExxx/GSExxx_family.soft.',
                        type=str, metavar='path')
    parser.add_argument('--state',
                        help='Path to a cached state of geotag.',
                        type=str, metavar='path.pkl',
                        default=f"{os.environ['HOME']}/geotag/"
                                f"{os.environ['USER']}.pkl")
    parser.add_argument('--update',
                        help='Overwrite the cache.',
                        action="store_true")
    parser.add_argument('--showKey',
                        help='Show key stroke in status bar.',
                        action="store_true")
    parser.add_argument('--version',
                        help='Display version.',
                        action="version",
                        version=App.__version__)
    args = parser.parse_args()
    args.user = os.environ['USER']
    if not os.environ.get('TMUX'):
        raise Exception('Please run geotag inside a tmux.')
    log_path, _ = os.path.split(args.log)
    if log_path == f"{os.environ['HOME']}/geotag":
        try:
            os.mkdir(log_path)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
    app = App(**vars(args))
    if not args.update and os.path.exists(args.state):
        try:
            with open(args.state, 'rb') as f:
                app.cache = pickle.load(f)
        except Exception as e:
            print('Failed to load previos state. Pass --update to overwrite.')
            raise
    try:
        print('Starting curses app ...')
        curses.wrapper(app.run)
    finally:
        print('Saving last state ...')
        with open(args.state, 'wb') as f:
            pickle.dump(app.cache, f)

if __name__ == "__main__":
    main()
