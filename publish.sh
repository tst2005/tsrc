#!/bin/bash

rm -fr dist
python setup.py sdist bdist_wheel
twine upload dist/*
