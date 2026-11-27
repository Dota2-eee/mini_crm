from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import Optional

from database import engine, get_db
import models, schemas, auth

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Мини-CRM для учёта клиентов и сделок")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Сервер Мини-CRM успешно работает!"}

# ================= АВТОРИЗАЦИЯ И ПОЛЬЗОВАТЕЛИ =================

@app.post("/register", response_model=schemas.UserOut)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    if user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=400, detail="Роль должна быть 'admin' или 'manager'")
    if db.query(models.User).filter(models.User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")
    
    new_user = models.User(
        username=user.username,
        password_hash=auth.hash_password(user.password),
        role=user.role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    
    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role, "username": user.username}

@app.get("/me", response_model=schemas.UserOut)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user

# ================= КЛИЕНТЫ (CRUD + ПОИСК) =================

@app.get("/clients")
def get_clients(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.Client)
    # Разграничение прав: менеджер видит только своих клиентов, админ — всех
    if current_user.role != "admin":
        query = query.filter(models.Client.owner_id == current_user.id)
    
    # Поиск по имени, телефону или компании
    if search:
        query = query.filter(
            or_(
                models.Client.name.ilike(f"%{search}%"),
                models.Client.phone.ilike(f"%{search}%"),
                models.Client.company.ilike(f"%{search}%")
            )
        )
    return query.all()

@app.post("/clients")
def create_client(
    client: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    new_client = models.Client(**client.model_dump(), owner_id=current_user.id)
    db.add(new_client)
    db.commit()
    db.refresh(new_client)
    return new_client

@app.put("/clients/{client_id}")
def update_client(
    client_id: int,
    client_data: schemas.ClientCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    if current_user.role != "admin" and client.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав на редактирование чужого клиента")
    
    for key, value in client_data.model_dump().items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client

@app.delete("/clients/{client_id}")
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(auth.require_admin)  # Удалять может только Админ
):
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")
    db.delete(client)
    db.commit()
    return {"message": "Клиент удалён"}

# ================= СДЕЛКИ (ВОРОНКА + ФИЛЬТРЫ) =================

@app.get("/deals")
def get_deals(
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(models.Deal)
    if current_user.role != "admin":
        query = query.filter(models.Deal.manager_id == current_user.id)
    if status:
        query = query.filter(models.Deal.status == status)
    if search:
        query = query.filter(models.Deal.title.ilike(f"%{search}%"))
    return query.all()

@app.post("/deals")
def create_deal(
    deal: schemas.DealCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if deal.status not in ["new", "in_progress", "won", "lost"]:
        raise HTTPException(status_code=400, detail="Недопустимый статус сделки")
    
    client = db.query(models.Client).filter(models.Client.id == deal.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Указанный клиент не существует")

    new_deal = models.Deal(**deal.model_dump(), manager_id=current_user.id)
    db.add(new_deal)
    db.commit()
    db.refresh(new_deal)
    return new_deal

# Смена статуса сделки (движение по воронке)
@app.patch("/deals/{deal_id}/status")
def update_deal_status(
    deal_id: int,
    status_data: schemas.DealStatusUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if status_data.status not in ["new", "in_progress", "won", "lost"]:
        raise HTTPException(status_code=400, detail="Недопустимый статус сделки")
    
    deal = db.query(models.Deal).filter(models.Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    if current_user.role != "admin" and deal.manager_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет прав изменять чужую сделку")
    
    deal.status = status_data.status
    db.commit()
    db.refresh(deal)
    return deal

@app.delete("/deals/{deal_id}")
def delete_deal(
    deal_id: int,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(auth.require_admin)
):
    deal = db.query(models.Deal).filter(models.Deal.id == deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    db.delete(deal)
    db.commit()
    return {"message": "Сделка удалена"}

# ================= ЗАМЕТКИ К СДЕЛКАМ =================

@app.get("/deals/{deal_id}/notes")
def get_notes(
    deal_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return db.query(models.Note).filter(models.Note.deal_id == deal_id).all()

@app.post("/notes")
def create_note(
    note: schemas.NoteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    deal = db.query(models.Deal).filter(models.Deal.id == note.deal_id).first()
    if not deal:
        raise HTTPException(status_code=404, detail="Сделка не найдена")
    
    new_note = models.Note(
        content=note.content,
        deal_id=note.deal_id,
        author_id=current_user.id
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return new_note

# ================= ДАШБОРД (АГРЕГАТНЫЙ ЗАПРОС) =================

@app.get("/dashboard")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    query = db.query(
        models.Deal.status,
        func.count(models.Deal.id).label("count"),
        func.sum(models.Deal.amount).label("total_amount")
    )
    # Менеджер видит статистику только по своим сделкам, Админ — по всей компании
    if current_user.role != "admin":
        query = query.filter(models.Deal.manager_id == current_user.id)
    
    results = query.group_by(models.Deal.status).all()
    
    summary = {
        "new": {"count": 0, "total_amount": 0.0},
        "in_progress": {"count": 0, "total_amount": 0.0},
        "won": {"count": 0, "total_amount": 0.0},
        "lost": {"count": 0, "total_amount": 0.0}
    }
    for row in results:
        summary[row.status] = {
            "count": row.count,
            "total_amount": float(row.total_amount or 0)
        }
    return summary
