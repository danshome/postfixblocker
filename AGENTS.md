# AGENTS

This repository contains a Python service and Angular web UI for managing a
database backed email block list for postfix.  Both PostGRESQL, and IBM DB2 11.5
need to be supported.

## Development instructions

- Do not modify the AGENTS.md file unless you ask first and explain what you would like to add to it and why. 
- Always strive to improve the project and make it better and easier to use.
- Don't assume the project follows best practices. If you find that it's not, then explain to the user why it's not following best practices and offer to fix the project.
- Before making any changes, start Docker services.
- Run unit tests with `pytest` from the repository root.
- Run db backend tests using `tests/test_db_backends.py`
- Run the E2E tests using `tests/e2e_test.py`
- If any of the unit tests, backend tests, or E2E tests fail, fix the issues before proceeding.
- Follow standard PEP8 style for Python code.
- After making any changes, always re-run the unit tests, backend tests, and E2E tests, and fix any issues.
- Always update documentation if necessary. 
- Always update the CHANGELOG.md file with the date and time of the change.
