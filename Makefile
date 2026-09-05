PY=python

.PHONY: setup ingest warehouse dbt score test all clean

setup:
	pip install -r requirements.txt

ingest:            ## CSV -> validated parquet
	$(PY) -m src.ingest.ingest_validate

warehouse:         ## parquet -> Postgres raw table (optional)
	$(PY) -m src.warehouse.load_postgres

dbt:               ## build staging + marts, run data quality tests
	cd dbt_project && dbt build

score:             ## inject labelled anomalies, fit detector, evaluate
	$(PY) -m src.models.train

test:
	pytest -q

all: ingest score test   ## full run without a database

clean:
	rm -rf data/processed/*.csv data/processed/*.json dbt_project/target
