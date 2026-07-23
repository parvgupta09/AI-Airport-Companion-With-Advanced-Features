from langchain.tools.retriever import create_retriever_tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from app.core.config import GEMINI_API_KEY, QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME

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

retriever = vector_store.as_retriever(search_kwargs={"k":3})

search_airport_policies = create_retriever_tool(
    retriever = retriever,
    name = "search_airport_policies",
    description = "Searches official airport policies, baggage rules, WI-Fi guides, lost baggeage, and special assistance procedures."
)