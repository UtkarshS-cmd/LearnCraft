# Offline-First Design

LearnCraft is designed to run primarily in offline mode. Main application data is stored locally in SQLite, while the UI remains available with local content and student progress.

Key principles:

- local first
- no remote dependency for core interactions
- resilient state sync queue
- future-ready network modes
