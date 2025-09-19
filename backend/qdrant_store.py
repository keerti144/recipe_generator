# backend/qdrant_store.py
import os
import uuid
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from dotenv import load_dotenv
from models import ChunkedDocument

load_dotenv()

class QdrantVectorStore:
    def __init__(self):
        # Initialize Qdrant client with extended timeout
        self.client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY"),
            timeout=120  # 2 minutes to avoid write timeouts
        )
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "my_rag_documents")
        self.vector_size = 3072  # text-embedding-3-large dimension

    def create_collection(self) -> bool:
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Collection {self.collection_name} created successfully")
            return True
        except Exception as e:
            print(f"Error creating collection: {e}")
            return False

    def add_documents(self, documents: List[ChunkedDocument], batch_size: int = 5) -> bool:
        """Add documents to the vector store in batches"""
        try:
            points: List[PointStruct] = []

            for doc in documents:
                if doc.embedding is None:
                    continue
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=doc.embedding,
                    payload={
                        "content": doc.content,
                        "doc_id": doc.id,
                        "metadata": doc.metadata
                    }
                )
                points.append(point)

            # Insert in batches
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch
                )
                print(f"Inserted batch {i // batch_size + 1} ({len(batch)} documents)")

            print(f"Added total {len(points)} documents to vector store")
            return True
        except Exception as e:
            print(f"Error adding documents: {e}")
            return False

    def search_similar(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """Search for similar documents"""
        try:
            search_result = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True
            )

            results = []
            for hit in search_result:
                results.append({
                    "content": hit.payload.get("content"),
                    "metadata": hit.payload.get("metadata"),
                    "score": hit.score,
                    "doc_id": hit.payload.get("doc_id")
                })
            return results
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []

    def delete_collection(self) -> bool:
        """Delete the collection"""
        try:
            self.client.delete_collection(collection_name=self.collection_name)
            print(f"Collection {self.collection_name} deleted successfully")
            return True
        except Exception as e:
            print(f"Error deleting collection: {e}")
            return False

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection"""
        try:
            info = self.client.get_collection(collection_name=self.collection_name)
            return {
                "name": info.name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status
            }
        except Exception as e:
            print(f"Error getting collection info: {e}")
            return {}
