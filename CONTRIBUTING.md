# Contributing

## Workflow

1. Create a branch from `main` (`feat/...`, `fix/...`, `docs/...`).
2. Make small, focused commits.
3. Open a pull request and fill in the template.

## Commit messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/), written in English:

```
<type>(<optional scope>): <short imperative summary>

<optional body explaining what and why>
```

Common types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

Examples:

- `feat(fetch): add Hacker News score threshold`
- `fix(email): handle missing recipient`
- `docs: update deployment steps`

## Code style

- Python code is linted and formatted with [Ruff](https://docs.astral.sh/ruff/):
  `ruff check .` and `ruff format .`
- Comments, docstrings, logs and documentation are written in English.
