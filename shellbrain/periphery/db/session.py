"""This module defines SQLAlchemy session-factory helpers for repository execution."""

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    """This function creates a reusable session factory bound to an engine."""

    return sessionmaker(bind=engine, future=True, expire_on_commit=False)
