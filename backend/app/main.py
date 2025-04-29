from fastapi import FastAPI, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from .pdf_processing import create_index_for_pdf, extract_text_from_pdf, initialize_llm
from .database import database, SessionLocal
from .models import PDFDocument
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from llama_index.core import StorageContext, load_index_from_storage
from llama_index.core.prompts import PromptTemplate
import os
import re

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .database import create_db
create_db()


@app.get("/")
def read_root():
    return {"message": "Backend is live!"}


def sanitize_filename(filename):
    return re.sub(r'[^a-zA-Z0-9.\-]', '_', filename)

class AskRequest(BaseModel):
    filename: str
    question: str

@app.post("/upload-pdf/")
async def upload_pdf(file: UploadFile, background_tasks: BackgroundTasks):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    sanitized_filename = sanitize_filename(file.filename)
    file_path = os.path.join("uploads", sanitized_filename)
    os.makedirs("uploads", exist_ok=True)
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            if not content:
                raise HTTPException(status_code=400, detail="Uploaded file is empty")
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
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
    try:
        background_tasks.add_task(create_index_for_pdf, file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create index: {str(e)}")
    return {"message": "File uploaded, indexing in background", "filename": sanitized_filename}

@app.post("/ask/")
async def ask_question(request: AskRequest):
    sanitized_filename = sanitize_filename(request.filename)
    file_path = os.path.join("uploads", sanitized_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {sanitized_filename}. Upload the file first.")
    if len(request.question.strip()) < 3:
        raise HTTPException(status_code=400, detail="Question is too short or vague.")
    index_path = os.path.join("indexes", sanitized_filename)
    if not os.path.exists(os.path.join(index_path, "docstore.json")):
        raise HTTPException(status_code=404, detail=f"Index not found for {sanitized_filename}. Please re-upload the file.")
    try:
        storage_context = StorageContext.from_defaults(persist_dir=index_path)
        index = load_index_from_storage(storage_context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load index: {str(e)}")
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

@app.on_event("startup")
async def startup():
    try:
        initialize_llm()
    except Exception as e:
        raise Exception(f"Failed to start server: {str(e)}")
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
