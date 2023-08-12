#!/bin/sh

sed -n "0,/# Usage/ p" README.md > README.new
echo >> README.new
./imaparms/imaparms.py --help-markdown | sed 's/^\(##*\) /#\1 /' >> README.new
mv README.new README.md
