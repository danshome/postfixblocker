# AGENTS

This repository contains a Python service and Angular web UI for managing a
Postfix block list.

## Development instructions

- Run unit tests with `pytest` from the repository root.
- Follow standard PEP8 style for Python code.
- The README previously referenced `tests/end_to_end_test.py`, but that file
  does not exist.
- `tests/e2e_demo.py` provides a simple end-to-end demonstration. It requires
  the docker-compose environment and will timeout quickly if services are
  unavailable.
- Update documentation and this file if new tests are added.
