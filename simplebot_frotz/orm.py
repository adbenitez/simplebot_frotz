from contextlib import contextmanager
from threading import Lock

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import relationship, sessionmaker


class Base:
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


Base = declarative_base(cls=Base)
_Session = sessionmaker()
_lock = Lock()


class Game(Base):
    name = Column(String(500), primary_key=True)
    player = Column(String(500), primary_key=True)
    chat_id = Column(Integer, nullable=False)


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    with _lock:
        session = _Session()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()


def init(path: str, debug: bool = False) -> None:
    """Initialize engine."""
    engine = create_engine(path, echo=debug)
    Base.metadata.create_all(engine)
    _Session.configure(bind=engine)
