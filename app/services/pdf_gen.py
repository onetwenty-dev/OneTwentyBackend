import os
import io
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
        """Assembles the premium PDF using Jinja2 and headless Edge/Chromium."""
        import jinja2
        import subprocess
        import tempfile
        import time

        start_time = time.time()
        logger.info("[PDF] Starting PDF generation...")

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
        range_label = "14-Day" # Default
        days_covered = report_data['metrics'].get('days_covered', 14)
        if days_covered <= 2: range_label = "1-Day"
        elif days_covered <= 8: range_label = "7-Day"
        elif days_covered <= 15: range_label = "14-Day"
        elif days_covered <= 31: range_label = "30-Day"
        elif days_covered <= 92: range_label = "90-Day"

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
        html_content = template.render(**template_vars)
        
        # 4. Browser Selection
        import platform
        system = platform.system()
        
        if system == "Windows":
            browser_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        else:
            # Common Linux paths (including ARM/Snap)
            paths = [
                "/usr/bin/chromium-browser",
                "/usr/bin/chromium",
                "/usr/bin/google-chrome",
                "/usr/bin/microsoft-edge",
                "/snap/bin/chromium", # For Ubuntu Snap
                "/usr/bin/brave-browser"
            ]
            browser_path = next((p for p in paths if os.path.exists(p)), "chromium")

        # 5. Execute Browser Headless
        with tempfile.TemporaryDirectory() as tmp_dir:
            html_path = os.path.join(tmp_dir, "report.html")
            pdf_path = os.path.join(tmp_dir, "report.pdf")
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Use aggressive stability flags for Linux ARM / CI environments
            args = [
                browser_path,
                "--headless", # Prefer standard headless for max compatibility on older ARM distros
                "--disable-gpu",
                "--no-sandbox",
                "--no-zygote", # Crucial for some Linux environments
                "--single-process", # Sometimes helps on low-RAM ARM devices
                "--disable-dev-shm-usage",
                "--disable-software-rasterizer",
                "--disable-extensions",
                "--disable-setuid-sandbox",
                f"--print-to-pdf={pdf_path}",
                "--no-pdf-header-footer",
                html_path
            ]
            
            logger.info(f"[PDF] Executing browser: {browser_path}")
            try:
                # Add a 30-second timeout to prevent the API from hanging forever.
                res = subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
                
                if not os.path.exists(pdf_path):
                    err_msg = f"Browser finished (0) but {pdf_path} MISSING.\nStderr: {res.stderr}"
                    logger.error(f"[PDF] {err_msg}")
                    raise Exception(err_msg)
                
                logger.info(f"[PDF] Successfully created PDF in {time.time() - start_time:.2f}s")
                with open(pdf_path, "rb") as f:
                    return f.read()
            except subprocess.TimeoutExpired:
                logger.error("[PDF] Browser timed out after 30s.")
                raise Exception("PDF generation timed out (browser hung). Check Chromium installation and dependencies.")
            except subprocess.CalledProcessError as e:
                err_msg = f"Browser failed (code {e.returncode}):\n{e.stderr}\n{e.stdout}"
                logger.error(f"[PDF] {err_msg}")
                raise Exception(err_msg)
            except Exception as e:
                logger.error(f"[PDF] Unexpected error: {str(e)}")
                raise e

    def upload_and_presign(self, pdf_content: bytes, tenant_id: str) -> str:
        """Uploads to S3 and returns a pre-signed URL valid for 1 hour."""
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
        return url
