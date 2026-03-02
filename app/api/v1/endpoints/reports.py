from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.api.deps import get_current_tenant_from_api_secret_or_jwt, get_mongo_db
from app.services.report import ReportService
from app.services.pdf_gen import PDFGenerator
from app.repositories.entries import EntriesRepository
from app.repositories.event import EventRepository
from app.repositories.user import UserRepository
from app.repositories.report import ReportRepository
from typing import Optional, List

router = APIRouter()


@router.get("/")
async def list_reports(
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    """
    Returns a list of all generated reports for the tenant.
    """
    repo = ReportRepository(db)
    reports = await repo.get_reports(tenant_id)
    return {
        "status": "success",
        "reports": reports
    }

@router.post("/generate")
async def generate_report(
    range: str = Query(..., regex="^(1d|1w|2w|3w|1m|3m|6m|9m|1y)$"),
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    """
    Generates a PDF report for the given range, uploads to S3, and returns a pre-signed URL.
    Ranges: 1d, 1w, 2w, 3w, 1m, 3m, 6m, 9m, 1y.
    """
    entries_repo = EntriesRepository()
    event_repo = EventRepository(db)
    user_repo = UserRepository()
    report_repo = ReportRepository(db)
    
    report_service = ReportService(entries_repo, event_repo)
    pdf_gen = PDFGenerator()
    
    # 1. Get Owner Details
    owner = user_repo.get_owner_details(int(tenant_id))
    if not owner:
        owner = {"name": "Valued User", "email": "No Email"}

    # 2. Aggregations
    try:
        report_data = await report_service.get_report_data(tenant_id, range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data aggregation failed: {str(e)}")

    # 3. Generate PDF
    try:
        pdf_content = pdf_gen.create_pdf(report_data, owner)
    except Exception as e:
        # Check if fpdf2 fonts are missing or other issues
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    # 4. Upload & Presign
    try:
        if not pdf_gen.bucket_name:
             # Fallback if bucket not configured in secrets
             raise HTTPException(status_code=500, detail="S3 Bucket not configured in settings.")
             
        presigned_url = pdf_gen.upload_and_presign(pdf_content, tenant_id)
        
        # 5. Save metadata to MongoDB
        report_meta = {
            "range": range,
            "report_url": presigned_url,
            "expires_in": 3600
        }
        await report_repo.save_report(tenant_id, report_meta)

        return {
            "status": "success",
            "range": range,
            "report_url": presigned_url,
            "expires_in": 3600
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 Upload failed: {str(e)}")
@router.get("/dashboard")
async def get_dashboard(
    range: str = Query("7d", regex="^(1d|1w|2w|3w|1m|3m|6m|9m|1y|7d|14d|30d|90d)$"),
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    """
    Returns dashboard data: metrics (TIR, GMI, CV, AVG), AGP chart data, and recent reports.
    """
    entries_repo = EntriesRepository()
    event_repo = EventRepository(db)
    report_service = ReportService(entries_repo, event_repo)
    
    # Map dashboard-specific ranges to service ranges if needed
    # (The service already handles many of these, but let's be safe)
    range_map = {
        "7d": "1w",
        "14d": "2w",
        "30d": "1m",
        "90d": "3m"
    }
    effective_range = range_map.get(range, range)
    
    # 1. Get Aggregated Data
    try:
        data = await report_service.get_report_data(tenant_id, effective_range)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data aggregation failed: {str(e)}")
        
    return {
        "status": "success",
        "range": range,
        "metrics": data["metrics"],
        "agp": data["agp_data"]
    }
