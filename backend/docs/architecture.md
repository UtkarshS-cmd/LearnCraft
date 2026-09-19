# LearnCraft Architecture

This project follows a layered application pattern:

- `app/core` holds configuration and shared runtime concerns.
- `app/models` contains the domain entities.
- `app/repositories` handles data access.
- `app/services` implements the business logic.
- `app/api` exposes routes for the application interface.
- `frontend/` stores the templates and static frontend assets.

The current application remains compatible with the legacy root-level Flask app while exposing a more scalable structure for future work.
