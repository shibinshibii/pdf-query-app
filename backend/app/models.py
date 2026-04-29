from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text  # Importing SQLAlchemy column types
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
    
    # Relationship to ChatMessage
    messages = relationship("ChatMessage", back_populates="pdf", cascade="all, delete-orphan")

# Model representing a chat message in the database
class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True, index=True)
    pdf_id = Column(Integer, ForeignKey('pdf_documents.id'))
    session_id = Column(String, index=True)  # For tracking guest sessions
    question = Column(Text)
    answer = Column(Text)
    sources = Column(Text)  # JSON string of sources
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationship back to PDFDocument
    pdf = relationship("PDFDocument", back_populates="messages")