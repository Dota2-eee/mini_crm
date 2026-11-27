import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from main import app
from database import Base, get_db
import auth

# Создаём временную тестовую базу в памяти, чтобы не засорять твой основной MS SQL Server
SQLALCHEMY_TEST_URL = "sqlite:///./test_crm.db"
engine = create_engine(SQLALCHEMY_TEST_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

# 1. UNIT-ТЕСТ (модульный): проверка шифрования и сверки паролей
def test_password_hashing():
    raw_password = "MySecretPassword123"
    hashed = auth.hash_password(raw_password)
    
    assert hashed != raw_password
    assert auth.verify_password(raw_password, hashed) is True
    assert auth.verify_password("WrongPassword", hashed) is False

# 2. ИНТЕГРАЦИОННЫЙ ТЕСТ №1: регистрация и вход с получением JWT-токена
def test_register_and_login():
    # Регистрируем пользователя
    reg_res = client.post("/register", json={
        "username": "test_manager",
        "password": "password123",
        "role": "manager"
    })
    assert reg_res.status_code == 200
    assert reg_res.json()["username"] == "test_manager"

    # Входим под этим пользователем
    login_res = client.post("/login", data={
        "username": "test_manager",
        "password": "password123"
    })
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

# 3. ИНТЕГРАЦИОННЫЙ ТЕСТ №2: создание клиента, сделки и проверка дашборда
def test_client_deal_and_dashboard_flow():
    # Регистрация и вход
    client.post("/register", json={"username": "admin_test", "password": "1234", "role": "admin"})
    token = client.post("/login", data={"username": "admin_test", "password": "1234"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Создаём клиента
    client_res = client.post("/clients", json={
        "name": "Иван Иванов",
        "phone": "+79991112233",
        "company": "ООО Тест"
    }, headers=headers)
    assert client_res.status_code == 200
    client_id = client_res.json()["id"]

    # Создаём сделку на 50 000 руб.
    deal_res = client.post("/deals", json={
        "title": "Продажа сайта",
        "amount": 50000,
        "status": "new",
        "client_id": client_id
    }, headers=headers)
    assert deal_res.status_code == 200

    # Проверяем, что дашборд посчитал сумму
    dash_res = client.get("/dashboard", headers=headers)
    assert dash_res.status_code == 200
    assert dash_res.json()["new"]["count"] == 1
    assert dash_res.json()["new"]["total_amount"] == 50000.0
