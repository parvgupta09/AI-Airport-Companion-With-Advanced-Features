import os
import sys
import logging
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.core.config import GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME

logging.basicConfig(level = logging.INFO)
logger = logging.getLogger(__name__)

POLICIES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "policies"))

def run_ingestion():

    logger.info("Loading policy documents...")
    loader = DirectoryLoader(POLICIES_DIR, glob="*.md", loader_cls=TextLoader)
    docs = loader.load()

    logger.info("Splitting text into chunks...")
    splitter = RecursiveCharacterTextSplitter(chunk_size = 500, chunk_overlap = 50)
    chunks = splitter.split_documents(docs)

    logger.info("Connecting to Qdrant and embedding documents...")
    embeddings = GoogleGenerativeAIEmbeddings(
        model = "models/gemini-embedding-001",
        google_api_key = GEMINI_API_KEY
    )

    QdrantVectorStore.from_documents(
        documents = chunks,
        embedding = embeddings,
        url = QDRANT_URL,
        api_key = QDRANT_API_KEY,
        collection_name = QDRANT_COLLECTION_NAME,
        timeout = 200.0
    )

    logger.info("Ingestion Complete")

if __name__ == "__main__":
    run_ingestion()