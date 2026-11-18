# Importing necessary modules and libraries
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks  # FastAPI framework and utilities
from fastapi.responses import JSONResponse  # For JSON responses
from fastapi.staticfiles import StaticFiles  # For serving static files
from pydantic import BaseModel  # For request validation
from .pdf_processing import create_index_for_pdf, extract_text_from_pdf, initialize_llm  # Custom PDF processing functions
from .snippet_generator import generate_snippet_clip  # Visual area snapshot generator
from .database import database, SessionLocal  # Database connection and session management
from .models import PDFDocument, ChatMessage  # Database models
from sqlalchemy.orm import Session  # SQLAlchemy session
from fastapi.middleware.cors import CORSMiddleware  # Middleware for handling CORS
from llama_index.core import StorageContext, load_index_from_storage  # For loading and managing indexes
from llama_index.core.prompts import PromptTemplate  # For creating custom prompts
import os  # For file and directory operations
import re  # For sanitizing filenames
import json  # For JSON operations
import urllib.request
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# Initialize FastAPI application
app = FastAPI()

# Get allowed origins from environment variables, defaulting to local dev url
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
origins = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allowed origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Mount the uploads and snippets directories to serve files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

os.makedirs("snippets", exist_ok=True)
app.mount("/snippets", StaticFiles(directory="snippets"), name="snippets")

# Import and initialize the database
from .database import create_db
create_db()  # Create database tables if they don't exist

# Define a root endpoint for health check
@app.get("/")
def read_root():
    return {"message": "Backend is live!"}  # Simple response to indicate the server is running

# Utility function to sanitize filenames by replacing invalid characters
def sanitize_filename(filename):
    return re.sub(r'[^a-zA-Z0-9.\-]', '_', filename)

def trigger_preprocessor(filename: str):
    """Notify the Go preprocessor service to extract metadata and render thumbnails."""
    preprocessor_url = os.getenv("PREPROCESSOR_URL", "http://localhost:8001")
    try:
        url = f"{preprocessor_url}/api/preprocess?filename={urllib.parse.quote(filename)}"
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=5):
            pass
    except Exception as e:
        print(f"[Preprocessor Notice] Could not trigger preprocessor: {e}")

# Pydantic model for validating the request body of the /ask/ endpoint
class AskRequest(BaseModel):
    filename: str  # Name of the file
    question: str  # Question to be asked
    session_id: str  # Guest session ID

# Endpoint to upload a PDF file
@app.post("/upload-pdf/")
async def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks):
    # Check if the uploaded file is a PDF
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    # Sanitize the filename and define the file path
    sanitized_filename = sanitize_filename(file.filename)
    file_path = os.path.join("uploads", sanitized_filename)
    os.makedirs("uploads", exist_ok=True)  # Ensure the uploads directory exists

    # Save the uploaded file to the server
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # Add the file information to the database if not already present
    db: Session = SessionLocal()
    try:
        existing_pdf = db.query(PDFDocument).filter(PDFDocument.filename == sanitized_filename).first()
        if not existing_pdf:
            pdf_document = PDFDocument(filename=sanitized_filename)
            db.add(pdf_document)
            db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()

    # Add a background task to create an index for the uploaded PDF
    try:
        background_tasks.add_task(create_index_for_pdf, file_path)
        background_tasks.add_task(trigger_preprocessor, sanitized_filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create index: {str(e)}")

    return {"message": "File uploaded, indexing in background", "filename": sanitized_filename}

# Endpoint to ask a question based on a PDF file
@app.post("/ask/")
def ask_question(request: AskRequest):
    # Sanitize the filename and check if the file exists
    sanitized_filename = sanitize_filename(request.filename)
    file_path = os.path.join("uploads", sanitized_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {sanitized_filename}. Upload the file first.")
    
    # Validate the question length
    if len(request.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question is too short or vague.")
    
    # Check if the index for the file exists
    index_path = os.path.join("indexes", sanitized_filename)
    if not os.path.exists(os.path.join(index_path, "docstore.json")):
        raise HTTPException(status_code=404, detail=f"Index not found for {sanitized_filename}. Please re-upload the file.")
    
    # Load the index from storage
    try:
        storage_context = StorageContext.from_defaults(persist_dir=index_path)
        index = load_index_from_storage(storage_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load index: {str(e)}")
    
    # Query the index using the provided question
    try:
        qa_prompt = PromptTemplate(
            "Instruction: Answer the question based on the provided context.\n"
            "Context: {context_str}\n"
            "Question: {query_str}\n"
            "Answer: "
        )
        query_engine = index.as_query_engine(
            streaming=False,
            similarity_top_k=4,
            text_qa_template=qa_prompt,
        )
        response = query_engine.query(request.question)
        
        # Extract salient terms for asynchronous layout-aware cropping in Go
        ans_str = str(response)
        
        # 1. Quoted and bold terms from markdown answer
        quoted_terms = re.findall(r'[\"\'\`\*]{1,2}([^\"\'\`\*]{3,40})[\"\'\`\*]{1,2}', ans_str)
        # 2. Capitalized phrases & proper nouns (e.g. "Calicut University", "Qmentr", "FastAPI")
        entity_phrases = re.findall(r'\b[A-Z][a-zA-Z0-9_\-\+]+(?:\s+[A-Z][a-zA-Z0-9_\-\+]+)*\b', ans_str)
        # 3. Clean content words from answer and question
        stop_words = {
            'based', 'provided', 'context', 'following', 'these', 'this', 'that', 'with', 'from',
            'have', 'been', 'were', 'what', 'when', 'where', 'which', 'about', 'also', 'some',
            'shibin', 'developer', 'python', 'role', 'graduated'
        }
        ans_words = [w for w in re.sub(r'[^\w\s]', ' ', ans_str).split() if len(w) > 3 and w.lower() not in stop_words]
        q_words = [w for w in re.sub(r'[^\w\s]', ' ', request.question).split() if len(w) > 3 and w.lower() not in stop_words]

        combined_terms = []
        for t in quoted_terms + entity_phrases + ans_words + q_words:
            t_clean = t.strip()
            if len(t_clean) >= 3 and t_clean.lower() not in stop_words and t_clean.lower() not in [x.lower() for x in combined_terms]:
                combined_terms.append(t_clean)

        terms_csv = ",".join(combined_terms[:12])

        # Extract sources from the response for progressive hydration
        sources = []
        seen_pages = set()
        for node in response.source_nodes:
            page = str(node.node.metadata.get("page_label", "N/A"))
            content = node.node.get_content()

            if page != "N/A" and page not in seen_pages:
                seen_pages.add(page)
                fetch_query = urllib.parse.urlencode({
                    "filename": sanitized_filename,
                    "page": page,
                    "query": request.question,
                    "terms": terms_csv,
                    "answer": ans_str[:400]
                })
                sources.append({
                    "page": page,
                    "text": content[:200] + "...",
                    "status": "pending",
                    "snippet_url": None,
                    "fetch_url": f"/api/snippet/crop?{fetch_query}"
                })

        # Graceful fallback: if no page label, include top node as text
        if not sources and response.source_nodes:
            top_node = response.source_nodes[0]
            sources.append({
                "text": top_node.node.get_content()[:200] + "...",
                "page": str(top_node.node.metadata.get("page_label", "N/A")),
                "status": "ready",
                "snippet_url": None
            })

        # Save the interaction to the database
        db: Session = SessionLocal()
        try:
            pdf = db.query(PDFDocument).filter(PDFDocument.filename == sanitized_filename).first()
            if pdf:
                chat_msg = ChatMessage(
                    pdf_id=pdf.id,
                    session_id=request.session_id,
                    question=request.question,
                    answer=str(response),
                    sources=json.dumps(sources)
                )
                db.add(chat_msg)
                db.commit()
        except Exception as e:
            db.rollback()
            print(f"Failed to save chat history: {e}")
        finally:
            db.close()

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    
    return {"answer": str(response), "sources": sources}

# Proxy endpoint to call Go preprocessor's visual snippet crop engine
@app.get("/api/snippet/crop")
def proxy_snippet_crop(filename: str, page: str, query: str = "", terms: str = "", answer: str = ""):
    preprocessor_url = os.getenv("PREPROCESSOR_URL", "http://localhost:8001")
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

# Endpoint to fetch chat history for a PDF and session
@app.get("/history/{filename}")
def get_chat_history(filename: str, session_id: str):
    sanitized_filename = sanitize_filename(filename)
    db: Session = SessionLocal()
    try:
        pdf = db.query(PDFDocument).filter(PDFDocument.filename == sanitized_filename).first()
        if not pdf:
            return []
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.pdf_id == pdf.id,
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.timestamp.asc()).all()
        
        history = []
        for msg in messages:
            history.append({
                "question": msg.question,
                "answer": msg.answer,
                "sources": json.loads(msg.sources) if msg.sources else []
            })
        return history
    finally:
        db.close()

# Endpoint to clear chat history
@app.delete("/history/{filename}")
def clear_chat_history(filename: str, session_id: str):
    sanitized_filename = sanitize_filename(filename)
    db: Session = SessionLocal()
    try:
        pdf = db.query(PDFDocument).filter(PDFDocument.filename == sanitized_filename).first()
        if pdf:
            db.query(ChatMessage).filter(
                ChatMessage.pdf_id == pdf.id,
                ChatMessage.session_id == session_id
            ).delete()
            db.commit()
        return {"message": "History cleared"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")
    finally:
        db.close()

# Event handler for application startup
@app.on_event("startup")
async def startup():
    try:
        initialize_llm()  # Initialize the language model
    except Exception as e:
        raise Exception(f"Failed to start server: {str(e)}")
    await database.connect()  # Connect to the database

# Event handler for application shutdown
@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()  # Disconnect from the database
