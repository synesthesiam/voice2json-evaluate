SHELL := bash

.PHONY: venv run check

all: venv

venv:
	scripts/create-venv.sh

run:
	scripts/run-evaluation.sh

check:
	scripts/check-code.sh dodo.py

clean:
	rm -f '.doit.db*'
