from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ВПИШИ СЮДА ИМЯ СЕРВЕРА ИЗ ШАГА 1 (вместо localhost, если у тебя другое)
SERVER_NAME = r"localhost\SQLEXPRESS"
DATABASE_NAME = "crm_db"


# Строка подключения к твоему MS SQL Server
SQLALCHEMY_DATABASE_URL = (
    f"mssql+pyodbc://@{SERVER_NAME}/{DATABASE_NAME}"
    "?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()