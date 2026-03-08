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
            "s3_key": report_data.get("s3_key"),
            "ai_summary": report_data.get("ai_summary"),
            "created_at": datetime.datetime.utcnow(),
            "expires_in": report_data.get("expires_in", 3600)
        }
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def get_latest_report_by_range(self, tenant_id: str, range_str: str) -> Optional[Dict[str, Any]]:
        """Finds the most recent report generated today for the given range."""
        today_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        doc = await self.collection.find_one({
            "tenant_id": tenant_id,
            "range": range_str,
            "created_at": {"$gte": today_start}
        }, sort=[("created_at", -1)])
        
        if doc:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("created_at"), datetime.datetime):
                doc["created_at"] = doc["created_at"].isoformat() + "Z"
            return doc
        return None
        
    async def get_reports(self, tenant_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        cursor = self.collection.find({"tenant_id": tenant_id}).sort("created_at", -1).limit(limit)
        reports = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if isinstance(doc.get("created_at"), datetime.datetime):
                doc["created_at"] = doc["created_at"].isoformat() + "Z"
            reports.append(doc)
        return reports
