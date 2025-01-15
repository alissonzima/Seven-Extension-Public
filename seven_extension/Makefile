install:
		@poetry install
format:
		@isort .
		@blue .
lint:
		@blue . --check --diff
		@isort . --check --diff
		@prospector --with-tool pydocstyle --doc-warning
test:
		@ward
sec:
		@pip-audit
