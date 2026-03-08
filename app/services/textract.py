import boto3
from app.core.config import settings
import logging

logger = logging.getLogger("OneTwenty")

class TextractService:
    def __init__(self):
        self.client = boto3.client(
            "textract",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    async def analyze_document(self, s3_bucket: str, s3_key: str) -> str:
        """
        Analyzes a document stored in S3 using Textract and returns the full text.
        """
        try:
            logger.info(f"[Textract] Starting analysis for s3://{s3_bucket}/{s3_key}")
            response = self.client.detect_document_text(
                Document={
                    'S3Object': {
                        'Bucket': s3_bucket,
                        'Name': s3_key
                    }
                }
            )
            
            full_text = ""
            for item in response.get("Blocks", []):
                if item["BlockType"] == "LINE":
                    full_text += item["Text"] + "\n"
            
            logger.info(f"[Textract] Extraction complete. {len(full_text)} characters.")
            return full_text.strip()
            
        except Exception as e:
            logger.error(f"[Textract] Analysis failed: {e}")
            return ""

textract_service = TextractService()
