#! /bin/bash -

outDir="$1"
gse="$2"

fl_path="$outDir/$gse"
mkdir -p "$fl_path"
cd "$fl_path"
soft_file="${gse}_family.soft.gz"
sPath="ftp://ftp.ncbi.nlm.nih.gov/geo/series/${gse:0:-3}nnn/$gse/soft/$soft_file"

wget -q "$sPath"
gzip -df "$soft_file"

>&2 echo "completed $gse in $outDir at $(date)"
