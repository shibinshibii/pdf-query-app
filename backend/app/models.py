import uuid
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

# Base class for all database models
Base = declarative_base()

class ChatSession(Base):
    __tablename__ = 'chat_sessions'

    id = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, default="New Conversation")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    documents = relationship(
        "ChatDocument", 
        back_populates="chat", 
        cascade="all, delete-orphan", 
        order_by="ChatDocument.created_at.asc()"
    )
    messages = relationship(
        "ChatMessage", 
        back_populates="chat", 
        cascade="all, delete-orphan", 
        order_by="ChatMessage.timestamp.asc()"
    )

class ChatDocument(Base):
    __tablename__ = 'chat_documents'

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey('chat_sessions.id', ondelete='CASCADE'), index=True)
    filename = Column(String, index=True)       # Sanitized file name on disk
    original_name = Column(String)              # User display name
    file_hash = Column(String, index=True)      # SHA-256 for deduplication
    page_count = Column(Integer, default=0)
    status = Column(String, default="ready")    # "indexing", "ready", "error"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    chat = relationship("ChatSession", back_populates="documents")

class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(String, ForeignKey('chat_sessions.id', ondelete='CASCADE'), index=True, nullable=True)
    pdf_id = Column(Integer, ForeignKey('pdf_documents.id', ondelete='CASCADE'), nullable=True)
    session_id = Column(String, index=True, nullable=True)  # Legacy guest session support
    question = Column(Text)
    answer = Column(Text)
    sources = Column(Text)  # JSON serialized array of source citations
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    chat = relationship("ChatSession", back_populates="messages")
    pdf = relationship("PDFDocument", back_populates="messages")

class PDFDocument(Base):
    __tablename__ = 'pdf_documents'

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="pdf", cascade="all, delete-orphan")
