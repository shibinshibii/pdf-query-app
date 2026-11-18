import os
from dotenv import load_dotenv
from databases import Database  # Importing the Database class for async database operations
from sqlalchemy import create_engine, text  # Importing create_engine to create a database engine
from sqlalchemy.orm import sessionmaker  # Importing sessionmaker to create database sessions
from .models import Base  # Importing the Base class from models to define database tables

load_dotenv()

# Database connection URL, defaulting to local SQLite if not provided in environment
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pdf_documents.db")

# Ensure directory exists if SQLite path has subdirectories (e.g. ./data/pdf_documents.db)
if SQLALCHEMY_DATABASE_URL.startswith("sqlite:///"):
    db_file_path = SQLALCHEMY_DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_file_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

# Creating an async database instance
database = Database(SQLALCHEMY_DATABASE_URL)

# Ensure thread-safety arguments are only passed to sqlite databases
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

# Creating a synchronous SQLAlchemy engine for database operations
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)

# Creating a session factory for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db():
    # Create all tables defined in the Base metadata
    Base.metadata.create_all(bind=engine)
    # Ensure columns exist if tables were created with an earlier schema
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE chat_messages ADD COLUMN chat_id VARCHAR"))
            conn.commit()
        except Exception:
            pass