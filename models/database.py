"""
models/database.py — SQLAlchemy instance shared across all models.

Import `db` from here everywhere — never create a second SQLAlchemy().
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
