from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.prompts import PromptTemplate
import os
from dotenv import load_dotenv

load_dotenv()

def create_index_for_pdf(file_path):
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        raise Exception(f"Invalid or empty file: {file_path}")
    if not file_path.lower().endswith('.pdf'):
        raise Exception("Only PDF files are supported.")
    try:
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
    except Exception as e:
        raise Exception(f"Failed to load PDF: {str(e)}")
    try:
        Settings.embed_model = GeminiEmbedding(
            model_name="models/embedding-001",
            api_key=os.getenv("GOOGLE_API_KEY")
        )
        index = VectorStoreIndex.from_documents(documents)
    except Exception as e:
        raise Exception(f"Failed to create index: {str(e)}")
    index_path = os.path.join("indexes", os.path.basename(file_path))
    try:
        os.makedirs(index_path, exist_ok=True)
        index.storage_context.persist(persist_dir=index_path)
        if not os.path.exists(os.path.join(index_path, "docstore.json")):
            raise Exception(f"Index not saved: {index_path}/docstore.json missing")
    except Exception as e:
        raise Exception(f"Failed to save index: {str(e)}")

def extract_text_from_pdf(file_path):
    try:
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        return " ".join([doc.text for doc in documents])
    except Exception as e:
        raise Exception(f"Failed to extract text: {str(e)}")

def initialize_llm():
    try:
        qa_prompt = PromptTemplate(
            "Instruction: Answer the question based on the provided context.\n"
            "Context: {context_str}\n"
            "Question: {query_str}\n"
            "Answer: "
        )
        llm = Gemini(
            model_name="models/gemini-1.5-flash",
            api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.5,
            max_tokens=256,
        )
        Settings.llm = llm
        Settings.text_qa_template = qa_prompt
    except Exception as e:
        raise Exception(f"Failed to initialize Gemini: {str(e)}")
