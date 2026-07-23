import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
from app.core.config import QDRANT_URL, QDRANT_API_KEY

logger = logging.getLogger(__name__)


class QdrantService:
    def __init__(self):

        self.collection_name = "airport_policies"

        try:
            self.client = QdrantClient(
                url = QDRANT_URL,
                api_key = QDRANT_API_KEY
            )
            self._ensure_collection_exists()
            logger.info("Successfully connected to Qdrant cloud")

        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {str(e)}")


    def _ensure_collection_exists(self):

        collections = self.client.get_collections().collections
        exists = any(col.name == self.collection_name for col in collections)

        if not exists:
            logger.info(f"Creating new Qdrant Collection: {self.collection_name}")
            self.client.create_collection(
                collection_name = self.collection_name,
                vector_config = models.VectorParams(
                    size = 768,
                    distance = models.Distance.COSINE
                )
            )


    def search_policies(self, query_vector: list[float], limit: int = 3) -> list[str]:

        try:
            search_result = self.client.search(
                collection_name = self.collection_name,
                query_vector = query_vector,
                limit = limit
            )

            return [hit.payload.get("text","") for hit in search_result]

        except Exception as e:
            logger.error(f"Qdrant Search Error : {str(e)}")
            return []


    def upsert_document(self, doc_id: str, vector: list[float], text_content: str, metadata: dict = None):

        payload = {"text", text_content}

        if metadata:
            payload.update(metadata)

        self.client_upsert(
            collection_name = self.collection_name,
            points = [
                models.PointStruct(
                    id = doc_id,
                    vector = vector,
                    payload = payload
                )
            ]
        )
        logger.info(f"Upserted document {doc_id} into Qdrant")

qdrant_service = QdrantService()
