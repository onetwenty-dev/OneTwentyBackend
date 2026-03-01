import os
import datetime
import boto3
from botocore.config import Config
from app.core.config import settings

import logging
logger = logging.getLogger("OneTwenty")

class PDFGenerator:
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'virtual'}
            )
        )
        self.bucket_name = settings.AWS_S3_BUCKET

    def create_pdf(self, report_data: dict, user_info: dict) -> bytes:
        """Assembles the premium PDF using Jinja2 and WeasyPrint (Browser-less)."""
        import jinja2
        import time
        from weasyprint import HTML, CSS

        start_time = time.time()
        logger.info("[PDF] Starting WeasyPrint generation...")

        # 1. Setup Jinja2
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(template_dir),
            extensions=['jinja2.ext.do', 'jinja2.ext.loopcontrols']
        )
        template = env.get_template("report_template.html")

        # 2. Prepare Data
        daily_data = report_data.get('daily_groups', [])
        total_pages = 1 + ((len(daily_data) + 1) // 2)
        
        # Determine range label
        days_covered = report_data['metrics'].get('days_covered', 14)
        if days_covered <= 2: range_label = "1-Day"
        elif days_covered <= 8: range_label = "7-Day"
        elif days_covered <= 15: range_label = "14-Day"
        elif days_covered <= 31: range_label = "30-Day"
        else: range_label = "90-Day"

        template_vars = {
            "range_label": range_label,
            "date_range_str": f"{report_data['start_date']} – {report_data['end_date']}",
            "patient_name": user_info.get("name", "Jane Doe"),
            "patient_dob": user_info.get("dob", "1990-05-14"),
            "metrics": report_data['metrics'],
            "agp": report_data['agp_data'],
            "daily_data": daily_data,
            "total_pages": total_pages,
            "generated_at": report_data['generation_date']
        }

        # 3. Render HTML
        logger.info(f"[PDF] Rendering template for {len(daily_data)} days...")
        render_start = time.time()
        html_content = template.render(**template_vars)
        logger.info(f"[PDF] Render complete in {time.time() - render_start:.2f}s")

        # 4. Generate PDF using WeasyPrint
        try:
            logger.info("[PDF] Executing WeasyPrint conversion...")
            wp_start = time.time()
            
            # WeasyPrint can render directly from the HTML string.
            # We provide base_url so it can find local assets if any exist.
            pdf_bytes = HTML(string=html_content, base_url=template_dir).write_pdf()
            
            logger.info(f"[PDF] Successfully created PDF ({len(pdf_bytes)} bytes) in {time.time() - start_time:.2f}s")
            return pdf_bytes
            
        except Exception as e:
            logger.error(f"[PDF] WeasyPrint error: {str(e)}")
            raise Exception(f"PDF generation failed via WeasyPrint: {str(e)}")

    def upload_and_presign(self, pdf_content: bytes, tenant_id: str) -> str:
        """Uploads to S3 and returns a pre-signed URL valid for 1 hour."""
        import time
        s3_start = time.time()
        filename = f"reports/{tenant_id}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=filename,
            Body=pdf_content,
            ContentType='application/pdf'
        )
        
        url = self.s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': self.bucket_name, 'Key': filename},
            ExpiresIn=3600
        )
        logger.info(f"[PDF] S3 upload and presign took {time.time() - s3_start:.2f}s")
        return url
