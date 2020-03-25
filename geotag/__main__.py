#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Module allowing for ``python -m geotag ...``."""
import argparse
import os
import pickle
import curses
import cProfile
from .geotag import App

def main():
    desc = 'Interface to quickly tag geo data sets.'
    parser = argparse.ArgumentParser(description=desc,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--rnaSeq',
                        help='.RDS table containing the extraction status of '
                        'RNASeq studies.', type=str, metavar='path',
                        default='/mnt/ribolution/user_worktmp/dominik.otto/'
                        'tumor-deconvolution-dream-challenge/'
                        'extraction_stats.tsv')
    parser.add_argument('--array',
                        help='.RDS table containing the extraction status of '
                        'microarray studies.', type=str, metavar='path',
                        default='/mnt/ribolution/user_worktmp/dominik.otto/'
                        'tumor-deconvolution-dream-challenge/'
                        'extraction_stats_array.tsv')
    parser.add_argument('--user',
                        help='The user name under which to write tags and log.',
                        type=str, metavar='name',
                        default=os.environ['USER'])
    parser.add_argument('--log',
                        help='The file path for the log.',
                        type=str, metavar='path',
                        default="/mnt/ribolution/user_worktmp/dominik.otto/"
                        f"geotag_collect/{os.environ['USER']}.log")
    parser.add_argument('--tags',
                        help='The file path for the tag yaml.',
                        type=str, metavar='path.yml',
                        default="/mnt/ribolution/user_worktmp/dominik.otto/"
                        f"geotag_collect/tags.yaml")
    parser.add_argument('--output',
                        help='The output file path.',
                        type=str, metavar='path.yml',
                        default="/mnt/ribolution/user_worktmp/dominik.otto/"
                        f"geotag_collect/{os.environ['USER']}.yml")
    parser.add_argument('--softPath',
                        help='Path to the soft file directory.',
                        type=str, metavar='path.yml',
                        default="/mnt/ribolution/user_worktmp/dominik.otto/"
                        "tumor-deconvolution-dream-challenge/studies-soft/")
    parser.add_argument('--state',
                        help='Path to a cached state of geotag.',
                        type=str, metavar='path.pkl',
                        default="/mnt/ribolution/user_worktmp/dominik.otto/"
                        f"geotag_collect/{os.environ['USER']}.pkl")
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
    if not os.environ.get('TMUX'):
        raise Exception('Please run geotag inside a tmux.')
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
    cProfile.run('main()', filename='prof.cprof')
