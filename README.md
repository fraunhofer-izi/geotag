Geotag is a utility to quickly tag studies and samples from
the [NCBI Gene Expression Omnibus](https://www.ncbi.nlm.nih.gov/geo/)
(GEO) on the command line.

# Features

 - Display custom data table with custom columns that help
   to tag a samples/rows.
 - Allow the user to modify the sample list to attach additional
   columns retrospectivly.
 - Quickly display sample specific part of the relevant soft file.
 - Filter and search data rows based on regular expressions.
 - Custom sorting and organization of columns.
 - Tag based line coloring for better overview and feedback to
   prevent mistakes.
 - Allow adjustment of tag definitions.
 - Allow creation of new tags that are shared between all users.
 - Self-contained documentation to show the user all features
   without the need to read a manual.
 - Undo/redo ability.
 - Automatic backups that do not accumulate indefinitely.
 - Select, show and tag multiple samples/rows simultaneously.
 - Allow to make a note per sample/row.
 - Quick and easy navigation.
 - Log all tag relevant user interactions.
 - Save the results automatically and in a human readable format.
 - Save last state upon exit to allow continuing where the work was
   left off upon restart.

# Installation
Geotag runs in Python 3.6 and and later versions. It uses the Python
[curses module](https://docs.python.org/3/howto/curses.html) for an
interactive user interface on the command line,
[tmux](https://github.com/tmux/tmux/wiki) to display and organize
multiple terminals and [less](http://www.greenwoodsoftware.com/less/)
to inspeact GEO soft files. Make sure tmux runs in 256 color mode,
e.g., by writing `set -g default-terminal "screen-256color"` into
your `~/.tmux.conf` befor starting tmux. You can install Geotag with
pip:
```
pip install git+ssh://git@ribogit.izi.fraunhofer.de/Dominik/geotag.git
```

# Input

The base of the tagging is a table of all samples that should be tagged. The table
must be tab-separated and contain the columns `gse` with the GEO Series accession
*GSExxx* and `id` with the GEO sample accession *GSMxxx*. Any additional columns
may provide supportive information. An example `<geo_sampe_table.tsv>`:
```tsv
gse id  platform_id characteristics
GSM1174473  GSE48305    tissue: peripheral blood
GSM1174472  GSE48305    tissue: peripheral blood
GSM3263619  GSE116912   cell: human iPSC
```
The table is passed with `--table <geo_sampe_table.tsv>`

Most information on the sample is accessible in the GEO soft files. In order
to make the content available to Geotag all relevant soft files need to
be organized such that the soft file of GSExxx is located in
`/path/to/the/soft/files/GSExxx/GSExxx_family.soft`. To download and
organize the soft files accordingly one could use the script `download_soft.sh`
with a list of line separated GSE numbers `<gse list>` by
```bash
cat <gse list> | xargs -n1 ./download_soft.sh /path/to/the/soft/files
```

# Output

Per default, Geotag writes all its output into the directory `~/geotag`.
There are four different files:
 1. The tag file, holding the tag descriptions (default `tag.yml`).
 2. The output file with the tags given to the samples (default `<user name>.yml`).
 3. A log-file loging many user actions (default `<user namer>.log`).
 4. A binary view file saving the view state of Geotag so you can continue
    where you left off after restarting Geotag (default `<user name>.pkl`).

An alternative output path for each of these files can be specified
respectively with the arguments `--tags`, `--output`, `--log` and `--state`.

## Format

The output file is a [yaml](https://yaml.org/) with the following
structure:
```yaml
tag definitions:
  <tag name>:
    col_width: <integer>
    desc: <str>
    editor: <str user name>
    key: <char>
    type: <"int" or "str">
  <next tag name ...>
tags:
  <tag name>:
    <gse numer>_<gsm number>(<uniquifying integer if neccesarry>): <value>
    <...>
  <next tag name ...>
```

## Saving and Backups

The output file is saved in an asynchronous thread after each tagging
action by the user. There is no feedback on whether the detached thread
successfully saved the file. If the user wants to make sure the latest
information is saved, a synchronous save can be triggered with the
key `s`.

All tagging actions can be undone with the key `u`. However, if geotag is
restarted, previous actions cannot be undone. To prevent
any loss of information a backup of the output file
and an appendix `.backup_<data and time>` is saved after every 10th
action. The user can restore a backup by removing the appendix
from the file name. Geotag will keep at most ten backups by removing
the oldest backup if this number is exceeded.

# Collaboration

To work together in a team, it is recommended to use a unique tag file
that all members can write to.
Whenever a member updates a tag description or
adds a new tag, the change becomes available to another member as soon
as she presses `t` to view the tag-dialog.

Note that all tag descriptions are also stored in the output file, and
upon a change of a tag description, all tags available to a user
will be written to the tag file. So to remove a tag, each member of
a team has to remove it.

If you want to share additional information between the team members,
e.g., the values they have tagged, it is recommended to write such
info to the `<geo_sampe_table.tsv>` e.g., through a periodically
repeated routine. The members can reload the displayed table by pressing `l`.

# Execution

Geotag needs to be run inside a [tmux](https://github.com/tmux/tmux/wiki)
session. This allows Geotag to display multiple soft files with
the reliable pager `less` and while using all the window splitting
and organizing features of tmux. If the output should be stored in
the default path, you can run Geotag with
```
python -m geotag --table <geo_sampe_table.tsv> --softPath /path/to/the/soft/files
```

# Troubleshooting

Some issues can be resolved by restarting Geotag with the `--update` option.
This will clear the current view state and leave the user at the top of
the table with default view settings. Another common issue is incomplete
keypress forwarding in the used terminal emulator. The key forwarded
to Geotag can be displayed in the status bar if you start it with `--showKey`.

# Documentation
Press `h` after getoag has loaded to receive help.
Sub-windows of Geotag list all available options at the top of the window.

# License

Copyright (C) 2019 Gesellschaft zur Foerderung der angewandten Forschung e.V.
acting on behalf of its Fraunhofer Institute for Cell Therapy and Immunology
(IZI).

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see http://www.gnu.org/licenses/.
