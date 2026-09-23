"""
SQLAlchemy declarative base.

Architecture Notes
------------------
All relational database models inherit from Base.

Alembic imports Base.metadata to compare the application's desired
schema with the current PostgreSQL schema.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy ORM models.
    """