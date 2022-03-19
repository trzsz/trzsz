#!/bin/sh

# sudo python3 -m pip install coverage

coverage run --source=. -m unittest discover && coverage report -m && coverage html
