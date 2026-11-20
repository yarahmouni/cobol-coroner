PYTHON ?= .venv/bin/python
SCREENSHOT_CHANNEL ?=
URL ?= http://127.0.0.1:8000

.PHONY: test test-all smoke smoke-ui demo zombie serve java-sample hooks junit-jars acceptance precommit traps demo-ebcdic coroner-gate screenshots deploy-check

test:
	$(PYTHON) -m pytest -q

test-all:
	$(PYTHON) -m pytest -q -m ''

acceptance:
	$(PYTHON) -m pytest -m slow -s

smoke:
	docker build -t coroner:smoke . && docker run --rm coroner:smoke

smoke-ui:
	@CLEAN_DIR=$$(bash scripts/clean_context.sh); \
	EXIT_CODE=0; \
	docker build --platform linux/amd64 -t coroner:smoke "$$CLEAN_DIR" || EXIT_CODE=$$?; \
	rm -rf "$$CLEAN_DIR"; \
	if [ $$EXIT_CODE -ne 0 ]; then exit $$EXIT_CODE; fi; \
	docker run --rm coroner:smoke python3 -m pytest -q -rs -p no:cacheprovider $(wildcard tests/test_ui*.py) tests/test_branch_reconciliation.py

demo:
	@$(PYTHON) -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java samples/credit-fees/java/CreditFees.java --schema samples/credit-fees/schema.json; exit $$?

zombie:
	@mkdir -p build/variants
	@$(PYTHON) -m coroner.catalog.legacy_variant samples/credit-fees/java/CreditFees.java build/variants/CreditFees.java
	@$(PYTHON) -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java build/variants/CreditFees.java --schema samples/credit-fees/schema.json; exit $$?

traps:
	@$(PYTHON) -m coroner traps

serve:
	$(PYTHON) -m uvicorn coroner.ui.app:app --host 127.0.0.1 --port 8000

java-sample:
	@mkdir -p build/java
	javac -d build/java samples/credit-fees/java/CreditFees.java
	INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv OUTPUT_FILE=build/java-rounding-ties-output.csv java -cp build/java CreditFees

hooks:
	@echo "git config core.hooksPath .githooks"

junit-jars:
	@$(PYTHON) scripts/download_junit.py

precommit:
	@JAVA_FILE=$${CORONER_PRECOMMIT_JAVA:-samples/credit-fees/java/CreditFees.java}; \
	$(PYTHON) -m coroner verify --cobol samples/credit-fees/CREDIT-FEES.cob --copybooks samples/credit-fees/copybooks --java "$$JAVA_FILE" --schema samples/credit-fees/schema.json --cases 500 --seed 42; exit $$?

demo-ebcdic:
	@$(PYTHON) -m coroner.demo_ebcdic

coroner-gate:
	$(PYTHON) -m coroner gate $(GATE_ARGS)

screenshots:
	SCREENSHOT_CHANNEL=$(SCREENSHOT_CHANNEL) $(PYTHON) scripts/make_screenshots.py

deploy-check:
	$(PYTHON) scripts/deploy_check.py --url $(URL)
