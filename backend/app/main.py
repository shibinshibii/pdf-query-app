# Importing necessary modules and libraries
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks  # FastAPI framework and utilities
from fastapi.responses import JSONResponse  # For JSON responses
from fastapi.staticfiles import StaticFiles  # For serving static files
from pydantic import BaseModel  # For request validation
from .pdf_processing import create_index_for_pdf, extract_text_from_pdf, initialize_llm  # Custom PDF processing functions
from .database import database, SessionLocal  # Database connection and session management
from .models import PDFDocument, ChatMessage  # Database models
from sqlalchemy.orm import Session  # SQLAlchemy session
from fastapi.middleware.cors import CORSMiddleware  # Middleware for handling CORS
from llama_index.core import StorageContext, load_index_from_storage  # For loading and managing indexes
from llama_index.core.prompts import PromptTemplate  # For creating custom prompts
import os  # For file and directory operations
import re  # For sanitizing filenames
import json  # For JSON operations
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

# Mount the uploads directory to serve files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create index: {str(e)}")

    return {"message": "File uploaded, indexing in background", "filename": sanitized_filename}

# Endpoint to ask a question based on a PDF file
@app.post("/ask/")
async def ask_question(request: AskRequest):
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
            similarity_top_k=2,
            text_qa_template=qa_prompt,
        )
        response = query_engine.query(request.question)
        
        # Extract sources from the response
        sources = []
        for node in response.source_nodes:
            sources.append({
                "text": node.node.get_content()[:200] + "...",
                "page": node.node.metadata.get("page_label", "N/A")
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

# Endpoint to fetch chat history for a PDF and session
@app.get("/history/{filename}")
async def get_chat_history(filename: str, session_id: str):
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
async def clear_chat_history(filename: str, session_id: str):
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
