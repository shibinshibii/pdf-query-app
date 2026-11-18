import os
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger("qdrant_manager")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = "pdf_chat_knowledge"
VECTOR_DIMENSION = 3072  # gemini-embedding-2 output vector dimension

def get_qdrant_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)

def init_qdrant_collection():
    """Ensure the target collection exists with HNSW cosine distance and keyword payload indexes."""
    client = get_qdrant_client()
    try:
        collections = client.get_collections().collections
        exists = any(c.name == COLLECTION_NAME for c in collections)
        if not exists:
            logger.info(f"Creating Qdrant collection: {COLLECTION_NAME}")
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=VECTOR_DIMENSION,
                    distance=models.Distance.COSINE
                )
            )
            # Create payload indexes for strict tenant isolation and filtering
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="chat_id",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="filename",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            client.create_payload_index(
                collection_name=COLLECTION_NAME,
                field_name="doc_hash",
                field_schema=models.PayloadSchemaType.KEYWORD
            )
            logger.info(f"Qdrant collection {COLLECTION_NAME} and payload indexes created successfully.")
        else:
            logger.info(f"Qdrant collection {COLLECTION_NAME} already exists.")
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant collection: {e}")
        # Non-fatal if server is still starting up
        pass

def delete_chat_vectors(chat_id: str):
    """Delete all vector points belonging to a specific chat session."""
    client = get_qdrant_client()
    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="chat_id",
                            match=models.MatchValue(value=chat_id)
                        )
                    ]
                )
            )
        )
        logger.info(f"Successfully deleted vectors for chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Failed to delete vectors for chat_id={chat_id}: {e}")

def delete_document_vectors(chat_id: str, filename: str):
    """Delete all vector points for a specific document inside a chat session."""
    client = get_qdrant_client()
    try:
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="chat_id",
                            match=models.MatchValue(value=chat_id)
                        ),
                        models.FieldCondition(
                            key="filename",
                            match=models.MatchValue(value=filename)
                        )
                    ]
                )
            )
        )
        logger.info(f"Successfully deleted vectors for doc={filename} in chat_id={chat_id}")
    except Exception as e:
        logger.error(f"Failed to delete vectors for doc={filename} in chat_id={chat_id}: {e}")

