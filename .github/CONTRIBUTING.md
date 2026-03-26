# Contributing to InkVault

Thanks for your interest in InkVault! This guide walks you through the development workflow and conventions we follow.

## Local Setup

### Prerequisites

- Python 3.13
- uv (package manager)
- Docker and docker-compose (for local Postgres and LocalStack)

### Getting Started

1. Clone the repository and navigate to it
2. Install dependencies with uv:
   ```
   uv sync
   ```
3. Start local services:
   ```
   docker-compose up -d
   ```
4. Run tests to verify everything works:
   ```
   pytest
   ```

## Running Tests

We use pytest for testing. Run tests from the project root:

```
pytest
pytest -v  # verbose output
pytest tests/test_specific_module.py  # run specific test file
pytest -k "test_name"  # run tests matching a pattern
```

Tests must pass before submitting a PR. Aim for meaningful test coverage, especially for extraction logic and data validation.

## Code Style

We use ruff for code quality. Format your code before committing:

```
ruff check .
ruff format .
```

These tools are configured in `pyproject.toml`. Pre-commit hooks run automatically, but you can also run them manually.

Style expectations:
- Type hints on all functions (enforced by ruff)
- Google-style docstrings on modules, classes, and public functions
- Structured logging with the Python logging module (never print statements)
- Pydantic models for validation only, no business logic in models
- Service functions accept dependencies as parameters

## Branching and Commits

### Branch Naming

Create a feature or fix branch for every non-trivial change:

```
git checkout -b feat/short-description
git checkout -b fix/short-description
git checkout -b refactor/short-description
```

Use lowercase and hyphens. Examples: `feat/document-classifier`, `fix/dynamodb-retry-logic`, `refactor/extract-validation`.

Only commit directly to main for trivial fixes (typos, config tweaks). Keep branches short-lived (hours to days).

### Commit Message Format

We follow Conventional Commits. Use this format:

```
type(scope): short description in imperative mood

Optional body explaining what and why, not how.
```

Rules:
- Subject line: imperative mood ("Add X", not "Added X"), under 50 characters, capitalized, no period
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`
- Scope: the module being changed (`models`, `db`, `api`, `services`, `pipeline`, `classifier`, `infra`)
- Body explains WHY, not HOW. The diff shows the how.

Examples:
- `feat(models): add Pydantic domain models for extraction results`
- `fix(validator): handle missing tax field in invoice extraction`
- `test(classifier): add unit tests for document classification`
- `docs(api): update endpoint documentation`

## Pull Request Workflow

1. Create a feature branch from main
2. Make atomic commits as you work (related changes in one commit, unrelated changes in separate commits)
3. Rebase onto main before pushing:
   ```
   git rebase main
   ```
4. Push your branch and open a PR on GitHub
5. Use a descriptive title (ideally following commit message convention)
6. Fill in the PR template with a summary and test plan
7. Self-review your diff before requesting review
8. Once approved, squash-merge into main and delete the branch

## Important Rules

- Never force push to main
- Never commit `.env`, credentials, or secrets
- Every commit on main must compile and tests must pass
- Main must always be in a working state
- `git pull --rebase` is configured for this repo

## Questions or Issues?

Check `CLAUDE.md` for detailed architecture, tech stack overview, and agent workflow guidance.
