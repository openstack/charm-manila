#!/usr/bin/make

clean:
	find . -iname '*.pyc' -delete
	find . -iname '__pycache__' -delete

default:
	echo "Doing nothing -- run 'make clean'"

all: default

