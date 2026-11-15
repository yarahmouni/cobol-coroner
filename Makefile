.PHONY: test smoke demo zombie serve

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
