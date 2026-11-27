from pydantic import BaseModel, Field
from typing import Optional

# --- Схемы для Пользователей ---
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4)
    role: str = Field(default="manager")  # 'admin' или 'manager'

class UserOut(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True

# --- Схемы для Клиентов ---
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    phone: str = Field(..., min_length=5, max_length=30)
    email: Optional[str] = None
    company: Optional[str] = None

# --- Схемы для Сделок ---
class DealCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    amount: float = Field(..., ge=0)  # Сумма не может быть меньше 0
    status: str = Field(default="new")  # new, in_progress, won, lost
    client_id: int

class DealStatusUpdate(BaseModel):
    status: str

# --- Схемы для Заметок ---
class NoteCreate(BaseModel):
    content: str = Field(..., min_length=1)
    deal_id: int