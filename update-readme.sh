#!/bin/sh

sed -n "0,/# Notes/ p" README.md > README.new
./imaparms/imaparms.py --help-markdown | sed "0,/# Notes/ d; $ d" >> README.new
mv README.new README.md
