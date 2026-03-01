from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any, Optional
import datetime

class ReportRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.reports
        
    async def save_report(self, tenant_id: str, report_data: Dict[str, Any]) -> str:
        doc = {
            "tenant_id": tenant_id,
            "range": report_data.get("range"),
            "report_url": report_data.get("report_url"),
            "created_at": datetime.datetime.utcnow(),
            "expires_in": report_data.get("expires_in", 3600)
        }
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
        
    async def get_reports(self, tenant_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"tenant_id": tenant_id}).sort("created_at", -1).limit(limit)
        reports = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("created_at"), datetime.datetime):
                doc["created_at"] = doc["created_at"].isoformat() + "Z"
            reports.append(doc)
        return reports
