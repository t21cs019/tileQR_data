.PHONY: all assemble validate ingest figures clean

all: validate ingest figures

# raw/ を作り直すので all には入れない。新しい計測を回収したときと、
# curation.yaml を書き換えたときに回す。
assemble:
	python scripts/assemble.py raw_data --apply --clean

validate:
	python scripts/validate.py

ingest:
	python scripts/ingest.py

figures:
	@for f in figures_src/fig_*.py; do echo "--- $$f"; python $$f --preset slide; done

clean:
	rm -rf derived/*.parquet derived/optima.csv figures/* COVERAGE.md
