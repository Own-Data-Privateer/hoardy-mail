#!/bin/sh -e

black $1 *.py hoardy_mail
mypy
pytest -k 'not slow'
pylint *.py hoardy_mail
./update-readme.sh
