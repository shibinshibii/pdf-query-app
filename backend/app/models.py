from sqlalchemy import Column, Integer, String, DateTime  # Importing SQLAlchemy column types
from sqlalchemy.ext.declarative import declarative_base  # Importing declarative_base to define models
from sqlalchemy.orm import relationship  # Importing relationship for ORM relationships
import datetime  # Importing datetime for default timestamp values

# Base class for all database models
Base = declarative_base()

# Model representing a PDF document in the database
class PDFDocument(Base):
    __tablename__ = 'pdf_documents'  # Name of the database table

    id = Column(Integer, primary_key=True, index=True)  # Primary key column
    filename = Column(String, index=True)  # Column to store the filename of the PDF
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)  # Column to store the upload timestamp