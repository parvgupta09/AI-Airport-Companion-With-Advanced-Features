import logging
from langchain.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from app.core.config import GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME

logger = logging.getLogger(__name__)

try:
    embeddings = GoogleGenerativeAIEmbeddings(
        model = "models/gemini-embedding-001",
        google_api_key = GEMINI_API_KEY
    )

    vector_store = QdrantVectorStore(
        embedding = embeddings,
        url = QDRANT_URL,
        api_key = QDRANT_API_KEY,
        collection_name = QDRANT_COLLECTION_NAME,
        timeout = 200.0
    )
except Exception as e:
    logger.error(f"Failed to initialize Qdrant Vector Store: {str(e)}")
    vector_store = None

@tool
def search_airport_policies(query: str) -> str:
    """
    Searches airport official rules, liquid limits, duty-free allowances, lost luggage procedures, Wi-Fi access, cancellation rebooking, layover transfers, security lockout or special assistance dispatch guidelines.

    Args:
        query: The specific policy or question the passenger is asking about.
    """

    if not vector_store:
        return "The airport policy is cuurently offline. Please try again later."

    try:
        logger.info(f"Searching Qdrant for : {query}")

        docs = vector_store.similarity_search(query, k=3)

        if not docs:
            return "I could not find any official airport policies matching that query"

        results = "\n\n".join([f"Document {i+1}: {doc.page_content}" for i, doc in enumerate(docs)])

        return f"Here is the official policy data I found:\n{results}"

    except Exception as e:
        logger.error(f"Qdrant searh failed during exceution: {str(e)}")
        return "I am currently unable to access the policy database due to a network timeout."