from sqlalchemy import Column, Integer, String, UniqueConstraint
from .db import Base


class SessionAccount(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, nullable=False)
    session_file = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint('phone', name='uq_sessions_phone'),
    )


class IpRange(Base):
    __tablename__ = "ip_ranges"

    id = Column(Integer, primary_key=True, index=True)
    prefix = Column(String, unique=True, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)


class AuthFlow(Base):
    __tablename__ = "auth_flows"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, nullable=False, index=True)
    phone_code_hash = Column(String, nullable=False)

