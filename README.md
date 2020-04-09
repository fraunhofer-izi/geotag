This project supllies a utility to quickly tag studies and samples from
the [NCBI Gene Expression Omnibus](https://www.ncbi.nlm.nih.gov/geo/).

# Installation
```
/usr/bin/python3 -m pip install --user pipx
/usr/bin/python3 -m pipx install git+ssh://git@ribogit.izi.fraunhofer.de/Dominik/geotag.git
```

# Upgrade
```
/usr/bin/python3 -m pipx upgrade geotag
```

# Execution
```
/usr/bin/python3 -m geotag
```

# Alternative Usage
There are issues for the installation, since we cannot use th lmod-python wich lacks a required function. So here **alternatively** do the following:
```
git clone git@ribogit.izi.fraunhofer.de:Dominik/geotag.git
/usr/bin/python3 -m pip install --user pandas numpy pyyaml
PYTHONPATH=$PWD/geotag /usr/bin/python3 -m geotag
```
If you want to start the application from another directory, make
sure the variable `PYTHONPATH` points to the geotag repo.

# Documentation
Press `h` after getoag has loaded to receive help.

# Tagging Data Sets

The tagging of the quality of GEO data sets is difficult to standardize between
different operators. Thus, let's collect different examples and the quality
that has been assigned to them.

| Tag  | Description | Example |
| ---- | ----------- | ------- |
| 0 | unrelated or no data | - |
| 1 | bad sample | - |
| 2 | bad annotation | - |
| 3 | cell mixture | - |
| 4 | modified cells | knock-down, spike-in, immortalized cell lines |
| 5 | - | - |
| 6 | stressed cells | drugs, vaccines |
| 7 | - | stimulated cells, progenitor cells (if they share a common coarse.cell.type) |
| 8 | - | - |
| 9 | perfectly pure and unmodified cells | DMSO controls, untreated cells |

All examples in the table provided above, are NOT fixed but should rather be
starting points for discussion.
