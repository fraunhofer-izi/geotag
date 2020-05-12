Geotag is a utility to quickly tag studies and samples from
the [NCBI Gene Expression Omnibus](https://www.ncbi.nlm.nih.gov/geo/)(geo).

# Installation
```
pip install git+ssh://git@ribogit.izi.fraunhofer.de/Dominik/geotag.git
```

# Input

Base of the tagging is a table of all samples that should be tagged. The table
must be tab seperated and contain the columns `gse` with the GEO Series accession
*GSExxx* and `id` with the GEO sample accession *GSMxxx*. Any additional columns
may provide supportive information. An example `<geo_sampe_table.tsv>`:
```tsv
gse	id	platform_id	characteristics
GSM1174473	GSE48305	tissue: peripheral blood
GSM1174472	GSE48305	tissue: peripheral blood
GSM3263619	GSE116912	cell: human iPSC
```
The table is passed with `--table <geo_sampe_table.tsv>`

Most information on the sample are accesible in the geo soft files. In order
to make the content available to geotag all relevant soft files need to
be organized such that the soft file of GSExxx is located in
`/path/to/the/soft/files/GSExxx/GSExxx_family.soft`. To download and
organize the soft files accordingly one could use the script `download_soft.sh`
with a list of line seperated GSE numbers `<gse list>` by
```bash
cat <gse list> | xargs -n1 ./download_soft.sh /path/to/the/soft/files
```

# Output

Per default geotag writes all its output into the dirctory `~/geotag`.
There are four differnt files:
 1. The tag file holding the tag descriptions (default `tag.yml`).
 2. The output file with the tags given to the samples (default `<user name>.yml`).
 3. A log-file loging many user actions (default `<user namer>.log`).
 4. A binary view file saving the view state of geotag so you can continue
    where you left off after restarting geotag (default `<user name>.pkl`).

An alternative output path for ach of these files can be specified
respectivly with the arguments `--tags`, `--output`, `--log` and `--state`.

# Collaboration

To work together in a team, it is recommended to use a unique tag file
that all members can write to.
Whenever a member updates a tag description or
adds a new tag, the change becomes available to another member as soon
as she presses `t` to view the tag-dialog.

Note that all tag descriptions are also stored in the output file and
upon a change of a tag description all tags available to a user
will be written to the tag file. So to remove a tag each member of
a team has to remove it.

If you want to share additional information between the member such
as the values they have tagged, it is recommendet to write such
info into the `<geo_sampe_table.tsv>` e.g. through a periodically
repeated routine. The member can reload their table by pressing `l`.

# Execution

Geotag needs to be run inside a [tmux](https://github.com/tmux/tmux/wiki)
session. This allows geotag to display multiple soft files with
the reliable pager `less` and while using all the window splitting
and organizing features of tmux. If the output should be stored in
the default path you can run geotag with
```
geotag --table <geo_sampe_table.tsv> --softPath /path/to/the/soft/files
```

# Troubleshooting

Some issues can be resolved by restarting geotag with the `--update` option.
This will clear the current view state and leave the user at the top of
the table with default view settings. Another common issue is incomplet
key press forwarding in the used terminal emulator. The key forwarded
to geotag can be displayed in the status bar if you start it with `--showKey`.

# Documentation
Press `h` after getoag has loaded to receive help.
Sub-windows of geotag list all available options at the top of the window.

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
