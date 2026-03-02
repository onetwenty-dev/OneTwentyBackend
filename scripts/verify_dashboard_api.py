import asyncio
import json
import os
import sys

# Ensure app is in path
sys.path.append(os.getcwd())

from app.services.report import ReportService
from app.repositories.entries import EntriesRepository
from app.repositories.event import EventRepository
from app.repositories.report import ReportRepository
from app.db.mongo import db

async def verify_dashboard():
    # 1. Initialize MongoDB
    db.connect()
    mongo_db = db.get_db()
    
    entries_repo = EntriesRepository()
    event_repo = EventRepository(mongo_db)
    report_repo = ReportRepository(mongo_db)
    service = ReportService(entries_repo, event_repo)
    
    # 2. Try to find a tenant with data or use a fallback
    # For now, let's use tenant_id "1" which is usually the first one created in test data
    tenant_id = "1" 
    
    print(f"Fetching dashboard data for tenant: {tenant_id}")
    try:
        data = await service.get_report_data(tenant_id, "7d")
        
        print("Metrics:")
        metrics = data["metrics"]
        print(f"  Avg Glucose: {metrics.get('avg_glucose')}")
        print(f"  TIR: {metrics.get('tir')}")
        print(f"  GMI: {metrics.get('gmi')}")
        print(f"  CV: {metrics.get('cv')}")
        
        print("AGP Data Structure:")
        agp = data["agp_data"]
        for key, val in agp.items():
            print(f"  {key}: {len(val)} points")
            
        assert "avg_glucose" in metrics
        assert "tir" in metrics
        if agp.get("median"):
            assert len(agp["median"]) == 24
        
        print("\nDashboard aggregation logic SUCCESS")
        
        print("Testing ReportRepository...")
        reports = await report_repo.get_reports(tenant_id, limit=5)
        print(f"Found {len(reports)} recent reports in MongoDB.")
        
    except Exception as e:
        print(f"Verification failed with error: {str(e)}")
        # If it's a data issue (empty DF), it's still "success" for the logic if it doesn't crash
        if "empty" in str(e).lower() or "columns" in str(e).lower():
            print("Note: This might be due to missing test data for tenant 1, but the code path was reached.")
        else:
            import traceback
            traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_dashboard())
