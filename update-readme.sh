#!/bin/sh -e

sed -n "0,/# Usage/ p" README.md > README.new
echo >> README.new
python3 -m imaparms.__main__ --help --markdown | sed '
s/^\(#\+\) /#\1 /
s/^\(#\+\) \(imaparms[^[({]*\) [[({].*/\1 \2/
' >> README.new
mv README.new README.md
pandoc -s -V pagetitle=README -f markdown -t html README.md > README.html
