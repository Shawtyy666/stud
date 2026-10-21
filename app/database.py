from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def make_engine(url: str):
    options = {"check_same_thread": False} if url.startswith("sqlite:") else {}
    return create_engine(url, connect_args=options)


def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
