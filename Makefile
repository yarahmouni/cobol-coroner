.PHONY: test smoke demo zombie serve java-sample hooks

test:
	.venv/bin/pytest -q

smoke:
	docker build -t coroner:smoke . && docker run --rm coroner:smoke

demo:
	@echo "demo: not available yet (planned for S1)" >&2; exit 2

zombie:
	@echo "zombie: not available yet (planned for S1)" >&2; exit 2

serve:
	@echo "serve: not available yet (planned for S2)" >&2; exit 2

java-sample:
	@mkdir -p build/java
	javac -d build/java samples/credit-fees/java/CreditFees.java
	INPUT_FILE=samples/credit-fees/fixtures/rounding-ties.csv OUTPUT_FILE=build/java-rounding-ties-output.csv java -cp build/java CreditFees

hooks:
	@echo "git config core.hooksPath .githooks"
