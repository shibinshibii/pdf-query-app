# Importing necessary modules and libraries
from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks  # FastAPI framework and utilities
from fastapi.responses import JSONResponse  # For JSON responses
from pydantic import BaseModel  # For request validation
from .pdf_processing import create_index_for_pdf, extract_text_from_pdf, initialize_llm  # Custom PDF processing functions
from .database import database, SessionLocal  # Database connection and session management
from .models import PDFDocument  # Database model for PDF documents
from sqlalchemy.orm import Session  # SQLAlchemy session
from fastapi.middleware.cors import CORSMiddleware  # Middleware for handling CORS
from llama_index.core import StorageContext, load_index_from_storage  # For loading and managing indexes
from llama_index.core.prompts import PromptTemplate  # For creating custom prompts
import os  # For file and directory operations
import re  # For sanitizing filenames

# Initialize FastAPI application
app = FastAPI()

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pdf-query-app-delta.vercel.app/"],  # Allowed origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

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

    # Add the file information to the database
    db: Session = SessionLocal()
    try:
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")
    
    return {"answer": str(response)}

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
