"""Mock UTM backend for MAiCampus — University Knowledge Base (UKB) + Facility Booking API.

A standalone FastAPI service backed by Postgres, run via Docker Compose. The MAiCampus
Flet app talks to it over HTTP to demonstrate the end-to-end system (Flow 3/4 UKB lookup
and Flow 6 facility booking with conflict detection).
"""
