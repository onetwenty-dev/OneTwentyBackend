from fastapi import APIRouter, Depends, HTTPException, Query
from app.api.deps import get_current_tenant_from_api_secret_or_jwt
from app.services.report import ReportService
from app.services.pdf_gen import PDFGenerator
from app.repositories.entries import EntriesRepository
from app.repositories.event import EventRepository
from app.repositories.user import UserRepository
from typing import Optional

router = APIRouter()

@router.post("/generate")
async def generate_report(
    range: str = Query(..., regex="^(1d|1w|2w|3w|1m|3m|6m|9m|1y)$"),
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt)
):
    """
    Generates a PDF report for the given range, uploads to S3, and returns a pre-signed URL.
    Ranges: 1d, 1w, 2w, 3w, 1m, 3m, 6m, 9m, 1y.
    """
    entries_repo = EntriesRepository()
    # EventRepository needs db instance
    from app.db.mongo import db
    event_repo = EventRepository(db.get_db())
    user_repo = UserRepository()
    
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
        return {
            "status": "success",
            "range": range,
            "report_url": presigned_url,
            "expires_in": 3600
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"S3 Upload failed: {str(e)}")
