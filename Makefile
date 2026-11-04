PYTHON ?= python

.PHONY: upgrade
# Refresh CI locks; update the consolidated ulmo-constraints.txt snapshot
# when the target platform changes. constraints.txt remains a small wrapper.
# Keep base.txt as a reference to base.in; runtime versions belong to edx-platform.
upgrade: export CUSTOM_COMPILE_COMMAND=make upgrade
upgrade:
	$(PYTHON) -m pip install -r requirements/pip.txt -r requirements/pip_tools.txt
	$(PYTHON) -m piptools compile --upgrade --allow-unsafe --strip-extras --no-emit-index-url --no-emit-trusted-host -o requirements/pip_tools.txt requirements/pip_tools.in
	$(PYTHON) -m piptools compile --upgrade --allow-unsafe --strip-extras --no-emit-index-url --no-emit-trusted-host -o requirements/ci.txt requirements/ci.in
	$(PYTHON) -m piptools compile --upgrade --allow-unsafe --strip-extras --no-emit-index-url --no-emit-trusted-host -o requirements/doc.txt requirements/doc.in
	$(PYTHON) -m piptools compile --upgrade --allow-unsafe --strip-extras --no-emit-index-url --no-emit-trusted-host --extra=test -o requirements/test.txt pyproject.toml requirements/test.in
	$(PYTHON) -m piptools compile --upgrade --allow-unsafe --strip-extras --no-emit-index-url --no-emit-trusted-host --extra=quality -o requirements/quality.txt pyproject.toml requirements/quality.in
