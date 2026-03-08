from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any, Optional
import datetime

class DocumentRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.documents
        
    async def save_document(self, tenant_id: str, doc_data: Dict[str, Any]) -> str:
        doc = {
            "tenant_id": tenant_id,
            "filename": doc_data.get("filename"),
            "s3_key": doc_data.get("s3_key"),
            "content_type": doc_data.get("content_type"),
            "file_size": doc_data.get("file_size"),
            "extracted_text": doc_data.get("extracted_text"),
            "created_at": datetime.datetime.utcnow()
        }
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
        
    async def get_documents(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"tenant_id": tenant_id}).sort("created_at", -1).limit(limit)
        docs = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("created_at"), datetime.datetime):
                doc["created_at"] = doc["created_at"].isoformat() + "Z"
            docs.append(doc)
        return docs
