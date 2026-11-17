.PHONY: test test-all smoke demo zombie serve java-sample hooks junit-jars acceptance precommit traps demo-ebcdic

test:
	.venv/bin/pytest -q

test-all:
	.venv/bin/pytest -q -m ''

acceptance:
	.venv/bin/pytest -m slow -s

smoke:
	docker build -t coroner:smoke . && docker run --rm coroner:smoke

demo:
	@.venv/bin/python -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java samples/credit-fees/java/CreditFees.java --schema samples/credit-fees/schema.json; exit $$?

zombie:
	@mkdir -p build/variants
	@.venv/bin/python -m coroner.catalog.legacy_variant samples/credit-fees/java/CreditFees.java build/variants/CreditFees.java
	@.venv/bin/python -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java build/variants/CreditFees.java --schema samples/credit-fees/schema.json; exit $$?

traps:
	@.venv/bin/python -m coroner traps

serve:
	.venv/bin/uvicorn coroner.ui.app:app --host 127.0.0.1 --port 8000

java-sample:
	@mkdir -p build/java
	javac -d build/java samples/credit-fees/java/CreditFees.java
	INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv OUTPUT_FILE=build/java-rounding-ties-output.csv java -cp build/java CreditFees

hooks:
	@echo "git config core.hooksPath .githooks"

junit-jars:
	@.venv/bin/python scripts/download_junit.py

precommit:
	@JAVA_FILE=$${CORONER_PRECOMMIT_JAVA:-samples/credit-fees/java/CreditFees.java}; \
	.venv/bin/python -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java "$$JAVA_FILE" --schema samples/credit-fees/schema.json --cases 500 --seed 42; exit $$?

demo-ebcdic:
	@.venv/bin/python -m coroner.demo_ebcdic
