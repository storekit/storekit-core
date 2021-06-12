
from sqlalchemy.ext.declarative import AbstractConcreteBase
from sqlalchemy import Column, String, ForeignKey, Float, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID

from sqlalchemy.ext.declarative import declarative_base

import datetime, uuid

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    uuid = Column('uuid', UUID(), default=uuid.uuid4, primary_key=True,
                  unique=True)
    email = Column('email', String, nullable=False, unique=True)
    password = Column('password', String, nullable=False)
    created_on = Column('created_on', DateTime(timezone=True),
                        default=datetime.datetime.utcnow())
    last_login = Column('last_login', DateTime(timezone=True),
                        onupdate=datetime.datetime.utcnow())
