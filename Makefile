.PHONY: all validate ingest figures clean

all: validate ingest figures

validate:
	python scripts/validate.py

ingest:
	python scripts/ingest.py

figures:
	@for f in figures/fig_*.py; do echo "--- $$f"; python $$f --preset slide; done

clean:
	rm -rf derived/*.parquet derived/optima.csv out/* COVERAGE.md
