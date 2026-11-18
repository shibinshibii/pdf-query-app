import os
import time
import logging
from typing import List
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, Settings, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from llama_index.core.prompts import PromptTemplate
from llama_index.core.vector_stores import MetadataFilters, ExactMatchFilter
from llama_index.vector_stores.qdrant import QdrantVectorStore
from google.api_core.exceptions import ResourceExhausted

from .qdrant_manager import get_qdrant_client, COLLECTION_NAME
from .database import SessionLocal
from .models import ChatDocument

load_dotenv()
logger = logging.getLogger("pdf_processing")

# QA Prompt template for Gemini synthesis
QA_PROMPT = PromptTemplate(
    "Instruction: Answer the question clearly and accurately based only on the provided context.\n"
    "If the answer cannot be found in the context, say so.\n"
    "Context: {context_str}\n"
    "Question: {query_str}\n"
    "Answer: "
)

class BatchedGeminiEmbedding(GeminiEmbedding):
    """
    Enhanced GeminiEmbedding that sends batches of texts in a single API call
    and applies exponential backoff on 429 ResourceExhausted rate limits.
    Prevents hitting the free-tier 100 RPM rate limit on large PDFs.
    """
    def _get_text_embeddings(self, texts: List[str]) -> List[List[float]]:
        results = []
        batch_size = 40  # Send up to 40 texts per single Google API call
        max_retries = 6

        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            success = False

            for attempt in range(max_retries):
                try:
                    res = self._model.embed_content(
                        model=self.model_name,
                        content=chunk,
                        task_type=self.task_type,
                        title=self.title,
                        request_options=self._request_options,
                    )
                    emb = res["embedding"]
                    if len(chunk) == 1 and isinstance(emb[0], float):
                        results.append(emb)
                    else:
                        results.extend(emb)
                    success = True
                    # Short pause between batches to stay comfortably below rate limit
                    time.sleep(0.3)
                    break
                except ResourceExhausted as e:
                    sleep_time = min(60, (attempt + 1) * 12)
                    logger.warning(
                        f"Google Gemini Embedding rate limit reached (429). Retrying in {sleep_time}s "
                        f"(attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(sleep_time)
                except Exception as e:
                    if "429" in str(e) or "quota" in str(e).lower():
                        sleep_time = min(60, (attempt + 1) * 12)
                        logger.warning(f"Rate limit exception: {e}. Retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                    else:
                        logger.error(f"Embedding error: {e}")
                        raise e

            if not success:
                raise Exception("Exceeded max retries for embedding generation due to rate limits.")

        return results

def initialize_llm():
    """Initialize Gemini LLM, embedding model, and global Settings."""
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY is not set!")

        llm = Gemini(
            model_name="models/gemini-flash-lite-latest",
            api_key=api_key,
            temperature=0.5,
            max_tokens=512,
        )
        embed_model = BatchedGeminiEmbedding(
            model_name="models/gemini-embedding-2",
            api_key=api_key,
        )
        node_parser = SentenceSplitter(
            chunk_size=512,
            chunk_overlap=50,
            include_metadata=True,
        )

        Settings.llm = llm
        Settings.embed_model = embed_model
        Settings.node_parser = node_parser
        Settings.text_qa_template = QA_PROMPT
        logger.info("Gemini LLM and Batched Embedding models initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {e}")
        raise Exception(f"Failed to initialize Gemini: {str(e)}")

def index_pdf_for_chat(file_path: str, chat_id: str, original_name: str, file_hash: str):
    """
    Parse, chunk, and embed a PDF into Qdrant scoped to a specific chat_id.
    Handles large PDFs gracefully with batching and updates ChatDocument status.
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        _update_doc_status(chat_id, os.path.basename(file_path), "error")
        raise Exception(f"Invalid or empty file: {file_path}")

    sanitized_filename = os.path.basename(file_path)

    try:
        # Mark as indexing
        _update_doc_status(chat_id, sanitized_filename, "indexing")

        # 1. Load PDF pages
        documents = SimpleDirectoryReader(input_files=[file_path]).load_data()
        page_count = len(documents)

        # 2. Attach chat isolation & file metadata to each document
        for doc in documents:
            doc.metadata["chat_id"] = str(chat_id)
            doc.metadata["filename"] = sanitized_filename
            doc.metadata["original_name"] = original_name
            doc.metadata["doc_hash"] = file_hash

        # 3. Parse into chunks
        node_parser = Settings.node_parser or SentenceSplitter(chunk_size=512, chunk_overlap=50, include_metadata=True)
        nodes = node_parser.get_nodes_from_documents(documents)

        # Ensure each node carries chat_id, filename, original_name, and page_label in metadata
        for node in nodes:
            node.metadata["chat_id"] = str(chat_id)
            node.metadata["filename"] = sanitized_filename
            node.metadata["original_name"] = original_name
            node.metadata["doc_hash"] = file_hash

        # 4. Ingest nodes into Qdrant
        client = get_qdrant_client()
        vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION_NAME)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)

        # Batch indexing for large documents
        batch_size = 40
        for i in range(0, len(nodes), batch_size):
            chunk_batch = nodes[i:i + batch_size]
            VectorStoreIndex(
                nodes=chunk_batch,
                storage_context=storage_context,
                embed_model=Settings.embed_model
            )
            time.sleep(0.2)

        # 5. Mark document as ready in database
        _update_doc_status(chat_id, sanitized_filename, "ready", page_count=page_count)
        logger.info(f"Successfully indexed {sanitized_filename} ({len(nodes)} chunks, {page_count} pages) for chat_id={chat_id}")

    except Exception as e:
        logger.error(f"Failed to index PDF {file_path} for chat {chat_id}: {e}")
        _update_doc_status(chat_id, sanitized_filename, "error")
        raise e

def _update_doc_status(chat_id: str, filename: str, status: str, page_count: int = 0):
    """Helper to update ChatDocument status in SQLite."""
    db = SessionLocal()
    try:
        doc = db.query(ChatDocument).filter(
            ChatDocument.chat_id == chat_id,
            ChatDocument.filename == filename
        ).first()
        if doc:
            doc.status = status
            if page_count > 0:
                doc.page_count = page_count
            db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update document status: {e}")
    finally:
        db.close()

def get_chat_query_engine(chat_id: str, similarity_top_k: int = 4):
    """
    Build a query engine strictly scoped to points belonging to `chat_id` in Qdrant.
    Guarantees no vectors from other chats are retrieved.
    """
    client = get_qdrant_client()
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION_NAME)
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store)

    # Multi-tenant isolation filter
    chat_filter = MetadataFilters(
        filters=[ExactMatchFilter(key="chat_id", value=str(chat_id))]
    )

    query_engine = index.as_query_engine(
        streaming=False,
        similarity_top_k=similarity_top_k,
        filters=chat_filter,
        text_qa_template=QA_PROMPT,
    )
    return query_engine
