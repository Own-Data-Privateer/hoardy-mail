#!/bin/sh -e

{
    sed -n "/# What is/,/# Usage/ p" README.md
    echo

    python3 -m hoardy_mail.__main__ --help --markdown | sed '
s/^\(#\+\) /#\1 /
s/^\(#\+\) \(hoardy-mail[^[({]*\) [[({].*/\1 \2/
'
} > README.new
mv README.new README.md
pandoc -s -V pagetitle=README -f markdown -t html README.md > README.html
