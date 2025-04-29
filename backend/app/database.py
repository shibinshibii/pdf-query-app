from databases import Database  # Importing the Database class for async database operations
from sqlalchemy import create_engine  # Importing create_engine to create a database engine
from sqlalchemy.orm import sessionmaker  # Importing sessionmaker to create database sessions
from .models import Base  # Importing the Base class from models to define database tables

# Database connection URL for SQLite
SQLALCHEMY_DATABASE_URL = "sqlite:///./pdf_documents.db"

# Creating an async database instance
database = Database(SQLALCHEMY_DATABASE_URL)

# Creating a synchronous SQLAlchemy engine for database operations
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})

# Creating a session factory for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db():
    # Create all tables defined in the Base metadata
    Base.metadata.create_all(bind=engine)