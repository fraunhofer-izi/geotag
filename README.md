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
PYTHONPATH=$PWD/geotag /usr/bin/python3 -m geotag
```
If you want to start the application from another directory, make
sure the variable `PYTHONPATH` points to the geotag repo.

# Documentation
Press `h` after getoag has loaded to receive help.
