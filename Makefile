.PHONY: test smoke demo zombie serve java-sample hooks junit-jars

test:
	.venv/bin/pytest -q

smoke:
	docker build -t coroner:smoke . && docker run --rm coroner:smoke

demo:
	@.venv/bin/python -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java samples/credit-fees/java/CreditFees.java --schema samples/credit-fees/schema.json; exit $$?

zombie:
	@mkdir -p build/variants
	@.venv/bin/python -m coroner.catalog.legacy_variant samples/credit-fees/java/CreditFees.java build/variants/CreditFees.java
	@.venv/bin/python -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java build/variants/CreditFees.java --schema samples/credit-fees/schema.json; exit $$?

serve:
	@echo "serve: not available yet (planned for S2)" >&2; exit 2

java-sample:
	@mkdir -p build/java
	javac -d build/java samples/credit-fees/java/CreditFees.java
	INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv OUTPUT_FILE=build/java-rounding-ties-output.csv java -cp build/java CreditFees

hooks:
	@echo "git config core.hooksPath .githooks"

junit-jars:
	@.venv/bin/python scripts/download_junit.py
