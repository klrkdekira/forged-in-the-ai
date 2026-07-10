"""SQLite storage: one file per campaign plus one app-level file (ADR-0005).

Pure package: no web or LLM imports. Consumed by app/ (which supplies
concrete file paths from settings) and later by engine/.
"""
