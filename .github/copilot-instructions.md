# Zen Repository Instructions

These instructions apply to all work in this repository.

## General Philosophy

- Follow existing architecture and coding patterns unless explicitly asked to redesign them.
- Prefer improving existing code over rewriting it.
- Keep changes focused on the requested task.
- Avoid unrelated refactors or formatting changes.
- Write maintainable, readable code over clever code.
- Minimize new dependencies unless there is a clear benefit.

---

# Definition of Done

A task is **not complete** until all applicable items below have been addressed.

- [ ] Implementation is complete.
- [ ] Relevant documentation has been updated.
- [ ] Version numbers have been updated if required.
- [ ] Project builds successfully (or build instructions have been provided if building is not possible).
- [ ] Relevant tests have been run or added.
- [ ] No obsolete code, documentation, or references remain.

---

# Version Management

This repository's release pipeline depends on the application version.

Whenever making changes that affect the shipped application, update the version before completing the task.

Affected files:

- `backend/version.py`
- `frontend/package.json`

Rules:

- Keep both version files synchronized.
- Never leave the repository with mismatched versions.
- Follow Semantic Versioning.

Version bump guidelines:

### Patch (`x.y.Z`)

Use for:

- Bug fixes
- Performance improvements
- Refactoring
- Internal improvements
- Security fixes
- Dependency updates
- Small UI improvements
- Documentation changes that accompany a release

### Minor (`x.Y.0`)

Use for:

- New features
- New API endpoints
- New UI functionality
- New configuration options
- Significant enhancements

### Major (`X.0.0`)

Use only for intentional breaking changes.

Do **not** bump versions for:

- README-only changes
- Comments
- CI configuration
- GitHub workflows
- Tests only
- Non-shipping development files

---

# Documentation

Documentation should evolve alongside the code.

Whenever functionality changes:

Update any affected documentation, including:

- README
- Installation instructions
- Configuration examples
- Environment variables
- API documentation
- Architecture documentation
- User guides
- Developer documentation

Never leave documentation describing behavior that no longer exists.

If a feature is added, document it.

If a feature is removed, remove its documentation.

If configuration changes, update all examples.

---

# Backend

When modifying backend code:

- Preserve API compatibility whenever possible.
- Validate all user input.
- Return consistent error responses.
- Use structured logging.
- Prefer explicit error handling.
- Avoid unnecessary database queries.
- Keep functions focused and small.

---

# Frontend

When modifying frontend code:

- Maintain a consistent UI.
- Keep components reusable.
- Handle loading states.
- Handle error states.
- Avoid unnecessary re-renders.
- Preserve accessibility.
- Keep responsive layouts working.

---

# Security

Always:

- Never hardcode secrets.
- Never commit credentials.
- Validate external input.
- Use secure defaults.
- Avoid introducing unnecessary attack surface.

---

# Testing

Whenever behavior changes:

- Update existing tests when necessary.
- Add new tests for new functionality when appropriate.
- Run relevant tests if possible.
- If tests cannot be run, clearly state that they were not verified.

Do not claim code has been tested unless it actually has.

---

# Code Quality

- Remove dead code encountered during changes.
- Keep imports clean.
- Avoid duplicate logic.
- Prefer descriptive variable names.
- Prefer composition over duplication.
- Keep functions single-purpose.
- Avoid premature optimization.

---

# Git & Pull Requests

Before considering work complete:

- Update documentation if needed.
- Update version numbers if needed.
- Ensure generated files remain synchronized.
- Ensure examples still work.
- Ensure no broken references remain.

---

# Communication

When making changes:

- Briefly explain significant design decisions.
- Mention any assumptions made.
- Mention any required follow-up work.
- Clearly identify breaking changes.

Never silently skip updating documentation or version numbers.

If something cannot be verified (tests, builds, runtime behavior), explicitly say so instead of assuming success.