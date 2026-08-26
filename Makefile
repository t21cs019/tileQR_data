.PHONY: all assemble validate ingest figures clean

all: validate ingest figures

# raw/ を作り直すので all には入れない。新しい計測を回収したときだけ回す。
assemble:
	python scripts/assemble.py raw_data --apply --clean-sweep

validate:
	python scripts/validate.py

ingest:
	python scripts/ingest.py

figures:
	@for f in figures/fig_*.py; do echo "--- $$f"; python $$f --preset slide; done

clean:
	rm -rf derived/*.parquet derived/optima.csv out/* COVERAGE.md
