from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

# 1. Таблица пользователей (Админ и Менеджер)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="manager", nullable=False)

# 2. Таблица клиентов
class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    phone = Column(String(30), nullable=False)
    email = Column(String(100), nullable=True)
    company = Column(String(100), nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

# 3. Таблица сделок (воронка продаж)
class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(150), nullable=False)
    amount = Column(Float, default=0.0, nullable=False)
    status = Column(String(30), default="new", nullable=False)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)

# 4. Таблица заметок к сделкам
class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)