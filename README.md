This project supllies a utility to quickly tag studies and samples from
the [NCBI Gene Expression Omnibus](https://www.ncbi.nlm.nih.gov/geo/).

# Installation
```
/usr/bin/python3 -m pip install --user pipx
/usr/bin/python3 -m pipx install git+ssh://git@ribogit.izi.fraunhofer.de/Dominik/geotag.git
```
If you have not setup to connect to gitlab by ssh you can also use the https-link:
```
/usr/bin/python3 -m pipx install git+https://ribogit.izi.fraunhofer.de/Dominik/geotag
```

# Upgrade
```
/usr/bin/python3 -m pipx upgrade geotag
```

# Execution
```
/usr/bin/python3 -m geotag
```

# Documentation
Press `h` after getoag has loaded to receive help.
