from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from app.api.deps import get_current_tenant_from_api_secret_or_jwt, get_mongo_db
from app.repositories.document import DocumentRepository
from app.services.s3 import s3_service
from app.services.textract import textract_service
from app.core.config import settings
import datetime

router = APIRouter()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    """
    Uploads a document to S3 and saves metadata in MongoDB.
    """
    repo = DocumentRepository(db)
    
    file_content = await file.read()
    file_size = len(file_content)
    
    # Generate S3 key: documents/{tenant_id}_{timestamp}_{filename}
    timestamp = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    s3_key = f"documents/{tenant_id}_{timestamp}_{file.filename}"
    
    try:
        # 1. Upload to S3
        s3_service.upload_file(file_content, s3_key, file.content_type)
        
        # 2. Trigger Textract Analysis (AI Feature)
        extracted_text = await textract_service.analyze_document(settings.S3_BUCKET_NAME, s3_key)
        
        # 3. Save metadata
        doc_meta = {
            "filename": file.filename,
            "s3_key": s3_key,
            "content_type": file.content_type,
            "file_size": file_size,
            "extracted_text": extracted_text
        }
        doc_id = await repo.save_document(tenant_id, doc_meta)
        
        # 3. Get a presigned URL for the response
        presigned_url = s3_service.get_presigned_url(s3_key)
        
        return {
            "status": "success",
            "document_id": doc_id,
            "filename": file.filename,
            "url": presigned_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/")
async def list_documents(
    tenant_id: str = Depends(get_current_tenant_from_api_secret_or_jwt),
    db = Depends(get_mongo_db)
):
    """
    Lists all documents for the user with fresh pre-signed URLs.
    """
    repo = DocumentRepository(db)
    docs = await repo.get_documents(tenant_id)
    
    for doc in docs:
        if doc.get("s3_key"):
            try:
                doc["url"] = s3_service.get_presigned_url(doc["s3_key"])
            except Exception:
                doc["url"] = None
                
    return {
        "status": "success",
        "documents": docs
    }
