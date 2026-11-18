from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import os
import re
import json
import hashlib
import uuid
import urllib.request
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from .database import database, SessionLocal, create_db
from .models import ChatSession, ChatDocument, ChatMessage, PDFDocument
from .pdf_processing import initialize_llm, index_pdf_for_chat, get_chat_query_engine
from .qdrant_manager import init_qdrant_collection, delete_chat_vectors, delete_document_vectors

load_dotenv()

app = FastAPI(title="PDF Reviewer API", version="2.0.0")

# Setup CORS
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:80,http://127.0.0.1:5173,http://127.0.0.1:80")
origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure runtime directories exist
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

os.makedirs("snippets", exist_ok=True)
app.mount("/snippets", StaticFiles(directory="snippets"), name="snippets")

# Initialize database schema
create_db()

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by replacing invalid characters with underscores."""
    name, ext = os.path.splitext(filename)
    clean_name = re.sub(r'[^a-zA-Z0-9.\-]', '_', name)
    return f"{clean_name}{ext.lower()}"

def compute_sha256(content: bytes) -> str:
    """Compute SHA-256 hash of byte content."""
    return hashlib.sha256(content).hexdigest()

def trigger_preprocessor(filename: str):
    """Notify the Go preprocessor service to extract metadata and render thumbnails."""
    preprocessor_url = os.getenv("PREPROCESSOR_URL", "http://preprocessor:8001")
    try:
        url = f"{preprocessor_url}/api/preprocess?filename={urllib.parse.quote(filename)}"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as e:
        print(f"[Preprocessor Notice] Could not trigger preprocessor: {e}")

# ==================== Pydantic Schemas ====================

class CreateChatRequest(BaseModel):
    title: Optional[str] = "New Conversation"

class UpdateChatRequest(BaseModel):
    title: str

class AskQuestionRequest(BaseModel):
    question: str

# Legacy Ask request
class LegacyAskRequest(BaseModel):
    filename: str
    question: str
    session_id: str

# ==================== Health Check ====================

@app.get("/")
def read_root():
    return {"message": "Backend is live with Qdrant multi-tenant RAG!", "version": "2.0.0"}

# ==================== Chat Session Management ====================

@app.post("/api/chats/")
def create_chat(request: CreateChatRequest):
    """Create a new chat conversation session."""
    db: Session = SessionLocal()
    try:
        chat = ChatSession(
            id=str(uuid.uuid4()),
            title=request.title or "New Conversation"
        )
        db.add(chat)
        db.commit()
        db.refresh(chat)
        return {
            "id": chat.id,
            "title": chat.title,
            "created_at": chat.created_at.isoformat(),
            "documents": [],
            "messages": []
        }
    finally:
        db.close()

@app.get("/api/chats/")
def list_chats():
    """List all chat sessions ordered by latest update."""
    db: Session = SessionLocal()
    try:
        chats = db.query(ChatSession).order_by(ChatSession.updated_at.desc()).all()
        result = []
        for c in chats:
            result.append({
                "id": c.id,
                "title": c.title,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
                "document_count": len(c.documents),
                "message_count": len(c.messages),
                "documents": [
                    {
                        "id": d.id,
                        "filename": d.filename,
                        "original_name": d.original_name,
                        "page_count": d.page_count,
                        "status": d.status
                    } for d in c.documents
                ]
            })
        return result
    finally:
        db.close()

@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    """Retrieve full details of a specific chat session including documents and messages."""
    db: Session = SessionLocal()
    try:
        chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")

        messages = []
        for m in chat.messages:
            sources = []
            if m.sources:
                try:
                    sources = json.loads(m.sources)
                except Exception:
                    sources = []
            messages.append({
                "id": m.id,
                "question": m.question,
                "answer": m.answer,
                "sources": sources,
                "timestamp": m.timestamp.isoformat()
            })

        documents = []
        for d in chat.documents:
            documents.append({
                "id": d.id,
                "filename": d.filename,
                "original_name": d.original_name,
                "page_count": d.page_count,
                "status": d.status,
                "created_at": d.created_at.isoformat()
            })

        return {
            "id": chat.id,
            "title": chat.title,
            "created_at": chat.created_at.isoformat(),
            "updated_at": chat.updated_at.isoformat(),
            "documents": documents,
            "messages": messages
        }
    finally:
        db.close()

@app.patch("/api/chats/{chat_id}")
def update_chat(chat_id: str, request: UpdateChatRequest):
    """Rename a chat session."""
    db: Session = SessionLocal()
    try:
        chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")
        chat.title = request.title.strip() or "Untitled Chat"
        db.commit()
        return {"id": chat.id, "title": chat.title}
    finally:
        db.close()

@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    """
    Delete a chat session, cascading deletion of its database records 
    AND all associated vectors in Qdrant.
    """
    db: Session = SessionLocal()
    try:
        chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # 1. Cascade delete vectors from Qdrant
        delete_chat_vectors(chat_id)

        # 2. Delete chat from SQLite (cascade deletes documents & messages)
        db.delete(chat)
        db.commit()
        return {"message": "Chat session and vector index deleted successfully"}
    finally:
        db.close()

# ==================== Multi-Document Upload per Chat ====================

@app.post("/api/chats/{chat_id}/documents")
async def upload_document_to_chat(
    chat_id: str, 
    file: UploadFile, 
    background_tasks: BackgroundTasks
):
    """Upload and attach a PDF document to a specific chat session."""
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    db: Session = SessionLocal()
    try:
        chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")

        # Read file content & compute hash
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        file_hash = compute_sha256(content)
        sanitized = sanitize_filename(file.filename)
        # Avoid filename collisions across uploads while preserving readability
        unique_filename = f"{chat_id[:8]}_{sanitized}"
        file_path = os.path.join("uploads", unique_filename)

        with open(file_path, "wb") as f:
            f.write(content)

        # Record document in database
        doc = ChatDocument(
            chat_id=chat_id,
            filename=unique_filename,
            original_name=file.filename,
            file_hash=file_hash,
            status="indexing"
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # Queue async indexing into Qdrant & thumbnailing in Go preprocessor
        background_tasks.add_task(
            index_pdf_for_chat, 
            file_path, 
            chat_id, 
            file.filename, 
            file_hash
        )
        background_tasks.add_task(trigger_preprocessor, unique_filename)

        return {
            "id": doc.id,
            "filename": doc.filename,
            "original_name": doc.original_name,
            "status": doc.status,
            "message": "File uploaded. Preparing document in background"
        }
    finally:
        db.close()

@app.delete("/api/chats/{chat_id}/documents/{document_id}")
def remove_document_from_chat(chat_id: str, document_id: int):
    """Remove a document from a chat session and purge its vectors from Qdrant."""
    db: Session = SessionLocal()
    try:
        doc = db.query(ChatDocument).filter(
            ChatDocument.id == document_id,
            ChatDocument.chat_id == chat_id
        ).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found in this chat")

        # 1. Purge vectors from Qdrant
        delete_document_vectors(chat_id, doc.filename)

        # 2. Remove document record
        db.delete(doc)
        db.commit()
        return {"message": f"Document {doc.original_name} removed from conversation"}
    finally:
        db.close()

# ==================== Multi-Document Q&A with Chat Isolation ====================

@app.post("/api/chats/{chat_id}/ask")
def ask_chat_question(chat_id: str, request: AskQuestionRequest):
    """
    Query the active chat with Gemini LLM + Qdrant.
    Vector retrieval is strictly constrained to documents belonging to `chat_id`.
    Returns multi-document source citations with progressive visual crop URLs.
    """
    question = request.question.strip()
    if len(question) < 2:
        raise HTTPException(status_code=400, detail="Question is too short.")

    db: Session = SessionLocal()
    try:
        chat = db.query(ChatSession).filter(ChatSession.id == chat_id).first()
        if not chat:
            raise HTTPException(status_code=404, detail="Chat session not found")

        if not chat.documents:
            raise HTTPException(status_code=400, detail="No documents uploaded yet. Upload a PDF to get started.")

        # Check if at least one document is ready or indexing
        ready_docs = [d for d in chat.documents if d.status == "ready"]
        if not ready_docs:
            indexing_docs = [d for d in chat.documents if d.status == "indexing"]
            if indexing_docs:
                return {
                    "answer": "Your document is still being prepared. Please give it a few seconds and try asking again.",
                    "sources": []
                }
            raise HTTPException(status_code=400, detail="We couldn't process this document. Please try re-uploading.")

        # Retrieve through Qdrant with chat_id filter
        query_engine = get_chat_query_engine(chat_id, similarity_top_k=5)
        response = query_engine.query(question)
        ans_str = str(response)

        # Extract salient terms for Go layout-aware visual cropping
        quoted_terms = re.findall(r'[\"\'\`\*]{1,2}([^\"\'\`\*]{3,40})[\"\'\`\*]{1,2}', ans_str)
        entity_phrases = re.findall(r'\b[A-Z][a-zA-Z0-9_\-\+]+(?:\s+[A-Z][a-zA-Z0-9_\-\+]+)*\b', ans_str)
        stop_words = {
            'based', 'provided', 'context', 'following', 'these', 'this', 'that', 'with', 'from',
            'have', 'been', 'were', 'what', 'when', 'where', 'which', 'about', 'also', 'some'
        }
        ans_words = [w for w in re.sub(r'[^\w\s]', ' ', ans_str).split() if len(w) > 3 and w.lower() not in stop_words]
        q_words = [w for w in re.sub(r'[^\w\s]', ' ', question).split() if len(w) > 3 and w.lower() not in stop_words]

        combined_terms = []
        for t in quoted_terms + entity_phrases + ans_words + q_words:
            t_clean = t.strip()
            if len(t_clean) >= 3 and t_clean.lower() not in stop_words and t_clean.lower() not in [x.lower() for x in combined_terms]:
                combined_terms.append(t_clean)

        terms_csv = ",".join(combined_terms[:12])

        # Build multi-document visual source citations
        sources = []
        seen_citations = set()

        for node in getattr(response, "source_nodes", []):
            meta = getattr(node.node, "metadata", {})
            doc_file = meta.get("filename", "")
            orig_name = meta.get("original_name", doc_file)
            page = str(meta.get("page_label", "1"))
            content = node.node.get_content()

            citation_key = f"{doc_file}_{page}"
            if doc_file and citation_key not in seen_citations:
                seen_citations.add(citation_key)
                fetch_query = urllib.parse.urlencode({
                    "filename": doc_file,
                    "page": page,
                    "query": question,
                    "terms": terms_csv,
                    "answer": ans_str[:400]
                })
                sources.append({
                    "document": orig_name,
                    "filename": doc_file,
                    "page": page,
                    "text": content[:220] + "...",
                    "status": "pending",
                    "snippet_url": None,
                    "fetch_url": f"/api/snippet/crop?{fetch_query}"
                })

        # Save interaction to SQLite
        chat_msg = ChatMessage(
            chat_id=chat_id,
            question=question,
            answer=ans_str,
            sources=json.dumps(sources)
        )
        db.add(chat_msg)

        # Auto-title chat from first question if untitled
        if chat.title in ("New Conversation", "New Chat", "Untitled Chat") and len(chat.messages) <= 1:
            clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', question).strip()
            chat.title = (clean_title[:32] + "...") if len(clean_title) > 32 else (clean_title or "Conversation")

        db.commit()

        return {"answer": ans_str, "sources": sources}
    finally:
        db.close()

# ==================== Visual Snippet Proxy (Go Preprocessor) ====================

@app.get("/api/snippet/crop")
def proxy_snippet_crop(filename: str, page: str, query: str = "", terms: str = "", answer: str = ""):
    """Proxy visual sub-rectangle citation cropping to Go microservice."""
    preprocessor_url = os.getenv("PREPROCESSOR_URL", "http://preprocessor:8001")
    params = urllib.parse.urlencode({
        "filename": filename,
        "page": page,
        "query": query,
        "terms": terms,
        "answer": answer
    })
    url = f"{preprocessor_url}/api/snippet/crop?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            preprocessor_public = os.getenv("PREPROCESSOR_PUBLIC_URL", "http://localhost:8001")
            if data.get("snippet_url") and data["snippet_url"].startswith("/thumbnails"):
                data["snippet_url"] = f"{preprocessor_public}{data['snippet_url']}"
            return data
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==================== Startup Event ====================

@app.on_event("startup")
async def startup():
    try:
        initialize_llm()
        init_qdrant_collection()
    except Exception as e:
        print(f"[Startup Notice] Initialization warning: {e}")
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
