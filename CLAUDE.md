# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## App Overview

`luxury_api` is a Frappe v16 app that exposes REST API endpoints on top of core Frappe (`User`, `Role`, `Has Role`, `User Permission`). It has no DocTypes, no hooks wired up, and no front-end assets — it's a pure whitelisted-API layer, run from the bench at `/home/trojan-technologies/frappe-bench` (see the bench-level `CLAUDE.md` for bench-wide commands like `bench start`, `bench migrate`, `bench build`, `bench run-tests`).

## Commands

All commands run from the bench root (`/home/trojan-technologies/frappe-bench`), not from `apps/luxury_api`.

```bash
# Install the app on the site (only needed once)
bench --site local.com install-app luxury_api

# Run tests for this app
bench --site local.com run-tests --app luxury_api

# Clear cache after changing hooks.py
bench --site local.com clear-cache
```

Linting/formatting, from `apps/luxury_api/` (after `pre-commit install`):

```bash
pre-commit run --all-files
ruff check luxury_api/
ruff format luxury_api/
```

Ruff config is in `pyproject.toml`: line length 110, tab indentation, target Python 3.14.

## Architecture

All application code lives under `luxury_api/api/`, one module per concern. Every public function is decorated with `@frappe.whitelist(...)` and called via `/api/method/luxury_api.api.<module>.<function>`.

- **`api/auth.py`** — `login(usr, pwd)` (`allow_guest=True`). Verifies credentials with `frappe.utils.password.check_password`, then runs the full `LoginManager` flow (`authenticate` + `post_login`) to establish a normal Frappe session/cookies — this is a login endpoint, not just a credential check. Returns the user's roles and User Permissions alongside profile fields, sourced from private helpers `_get_roles` / `_get_user_permissions` in the same file. Only proceeds to `post_login()` if the user is enabled; disabled users get `active: false` back without a session being created.

- **`api/user.py`** — `get_users(role=None)`, an authenticated (non-guest) directory lookup. Excludes `Administrator` and Website Users, optionally filters to a given `role` (validated to exist via `_validate_role`, raising `frappe.DoesNotExistError` if not). Batches roles and permissions lookups across all matched users in two queries (`_fetch_roles_map`, `_fetch_permissions_map`) rather than querying per-user, and stitches results back together in Python — follow this batching pattern for any similar list-with-related-data endpoint added here.

When adding a new endpoint module, follow the existing convention: one file per resource under `api/`, whitelisted top-level functions as the public surface, and `_`-prefixed module-private helpers for query logic — keep bulk lookups batched (`frappe.get_all` with `["in", ...]` filters) instead of looping per record.

`hooks.py` is currently the stock scaffold (no `doc_events`, `scheduler_events`, or fixtures configured) — this app does not yet hook into any DocType lifecycle or run scheduled jobs.
