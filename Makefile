PYTHON ?= .venv/bin/python
SCREENSHOT_CHANNEL ?=
URL ?= http://127.0.0.1:8000

.PHONY: test test-serial test-all smoke smoke-ui demo zombie serve java-sample hooks junit-jars pbt acceptance precommit traps demo-ebcdic coroner-gate screenshots deploy-check static-page

# Default suite in parallel (pytest-xdist). --dist loadfile keeps every test file on one worker, in file order,
# so the module fixtures and the order of the tests of a file are the same as in a serial run.
test:
	$(PYTHON) -m pytest -q -n auto --dist loadfile

test-serial:
	$(PYTHON) -m pytest -q

test-all:
	$(PYTHON) -m pytest -q -m ''

acceptance:
	$(PYTHON) -m pytest -m slow -s

smoke:
	docker build -t coroner:smoke . && docker run --init --rm coroner:smoke

smoke-ui:
	@CLEAN_DIR=$$(bash scripts/clean_context.sh); \
	EXIT_CODE=0; \
	docker build --platform linux/amd64 -t coroner:smoke "$$CLEAN_DIR" || EXIT_CODE=$$?; \
	rm -rf "$$CLEAN_DIR"; \
	if [ $$EXIT_CODE -ne 0 ]; then exit $$EXIT_CODE; fi; \
	docker run --init --rm coroner:smoke python3 -m pytest -q -rs -p no:cacheprovider $(wildcard tests/test_ui*.py) tests/test_branch_reconciliation.py

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

# Property-based test of the two T1 Java ports (jqwik on the JUnit Platform console launcher)
T1_JAVA := samples/traps/T1-ebcdic-match-merge/java
PBT_CP := build/junit/junit-platform-console-standalone-6.1.3.jar:build/junit/jqwik-api-1.10.2.jar:build/junit/jqwik-engine-1.10.2.jar

pbt: junit-jars
	@mkdir -p build/pbt/faulty build/pbt/correct build/pbt/property
	@javac -encoding UTF-8 -nowarn -d build/pbt/faulty $(T1_JAVA)/faulty/MatchMerge.java
	@javac -encoding UTF-8 -nowarn -d build/pbt/correct $(T1_JAVA)/correct/MatchMerge.java
	@javac -encoding UTF-8 -Xlint:all -cp $(PBT_CP) -d build/pbt/property $(T1_JAVA)/property/MatchMergeProperties.java
	@java -Dpbt.faulty=build/pbt/faulty -Dpbt.correct=build/pbt/correct -cp "$(PBT_CP):build/pbt/property:$(T1_JAVA)/property" \
		org.junit.platform.console.ConsoleLauncher execute --include-engine=jqwik --select-class=MatchMergeProperties \
		--details=tree --disable-banner --disable-ansi-colors

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

static-page:
	@test -n "$(BASE)" || { echo "BASE=<dir with runs/ and runs/trap_catalog.json> is required"; exit 2; }
	@test -n "$(COMMIT)" || { echo "COMMIT=<commit id> is required"; exit 2; }
	$(PYTHON) scripts/build_static_page.py --base "$(BASE)" --out docs/static --commit "$(COMMIT)"
