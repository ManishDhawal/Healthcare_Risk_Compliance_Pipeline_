PY=python

.PHONY: setup ingest test

setup:
	pip install -r requirements.txt

ingest:
	$(PY) src/ingest/ingest_validate.py

test:
	pytest -q
