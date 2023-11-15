#!/bin/sh -e

sed -n "0,/# Usage/ p" README.md > README.new
echo >> README.new
python3 -m imaparms.__main__ --help --markdown | sed 's/^\(##*\) /#\1 /' >> README.new
mv README.new README.md
pandoc -f markdown -t html README.md > README.html
