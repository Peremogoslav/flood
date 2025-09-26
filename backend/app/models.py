from sqlalchemy import Column, Integer, String, UniqueConstraint
from .db import Base


class SessionAccount(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, nullable=False)
    session_file = Column(String, nullable=True)
    session_string = Column(String, nullable=True)
    user_id = Column(Integer, nullable=True, index=True)

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
    is_admin = Column(Integer, nullable=False, default=0)


class AuthFlow(Base):
    __tablename__ = "auth_flows"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, unique=True, nullable=False, index=True)
    phone_code_hash = Column(String, nullable=False)


class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    min_delay = Column(Integer, nullable=False, default=10)
    max_delay = Column(Integer, nullable=False, default=15)
    randomize_chats = Column(Integer, nullable=False, default=1)  # 1=true, 0=false
    use_images = Column(Integer, nullable=False, default=0)

