import os
import datetime
import boto3
from botocore.config import Config
from app.core.config import settings

import logging
logger = logging.getLogger("OneTwenty")

from app.services.s3 import s3_service

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_AVAILABLE = True
except Exception as e:
    logger.warning(f"[PDF] WeasyPrint dependencies (GTK) not found: {e}. Falling back to fpdf2 for Windows.")
    WEASYPRINT_AVAILABLE = False

try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False

class PDFGenerator:
    def __init__(self):
        # We can keep empty or just remove entirely if not needed elsewhere
        pass

    def create_pdf(self, report_data: dict, user_info: dict) -> bytes:
        """Assembles the premium PDF using Jinja2 and WeasyPrint (Browser-less)."""
        import jinja2
        import time

        start_time = time.time()
        logger.info("[PDF] Starting WeasyPrint generation...")

        # 1. Prepare Data
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
            "generated_at": report_data['generation_date'],
            "ai_summary": report_data.get("ai_summary")
        }

        if WEASYPRINT_AVAILABLE:
            # 3. Render HTML
            import jinja2
            template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
            env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(template_dir),
                extensions=['jinja2.ext.do', 'jinja2.ext.loopcontrols']
            )
            template = env.get_template("report_template.html")

            logger.info(f"[PDF] Rendering template for {len(daily_data)} days...")
            render_start = time.time()
            html_content = template.render(**template_vars)
            logger.info(f"[PDF] Render complete in {time.time() - render_start:.2f}s")

            try:
                logger.info("[PDF] Executing WeasyPrint conversion...")
                pdf_bytes = HTML(string=html_content, base_url=template_dir).write_pdf()
                logger.info(f"[PDF] Successfully created PDF ({len(pdf_bytes)} bytes) in {time.time() - start_time:.2f}s")
                return pdf_bytes
            except Exception as e:
                logger.error(f"[PDF] WeasyPrint error: {str(e)}")
                # If WeasyPrint specifically fails during write_pdf, we can still try fpdf2 if available
                if FPDF_AVAILABLE:
                    logger.info("[PDF] WeasyPrint failed during conversion, falling back to fpdf2...")
                    return self._create_fallback_pdf(template_vars)
                raise
        elif FPDF_AVAILABLE:
            logger.info("[PDF] WeasyPrint unavailable, using fpdf2 fallback directly...")
            return self._create_fallback_pdf(template_vars)
        else:
            raise Exception("Neither WeasyPrint nor fpdf2 are available for PDF generation.")

    def _create_fallback_pdf(self, vars: dict) -> bytes:
        """Simple pure-Python fallback for Windows dev environments without GTK."""
        def sanitize(text: str) -> str:
            if not text: return ""
            # 1. Replace known offenders for better legibility
            replacements = {
                '\u2013': '-', # en-dash
                '\u2014': '-', # em-dash
                '\u2018': "'", # left single quote
                '\u2019': "'", # right single quote
                '\u201c': '"', # left double quote
                '\u201d': '"', # right double quote
            }
            for char, rep in replacements.items():
                text = text.replace(char, rep)
            # 2. Force latin-1 for safety with standard fpdf2 fonts
            # This replaces any other obscure symbols with '?' instead of crashing
            return text.encode('latin-1', 'replace').decode('latin-1')

        pdf = FPDF()
        pdf.add_page()
        
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, sanitize(f"Clinical Summary Report - {vars['patient_name']}"), ln=True, align="C")
        pdf.set_font("Arial", "", 12)
        pdf.cell(190, 10, sanitize(f"Range: {vars['date_range_str']}"), ln=True, align="C")
        pdf.ln(10)

        # AI Summary Section
        if vars.get("ai_summary"):
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "OneTwenty Clinical Brief", ln=True)
            pdf.set_font("Arial", "", 11)
            summary = vars["ai_summary"]
            pdf.multi_cell(0, 7, sanitize(f"Overview: {summary.get('summary', 'No summary available.')}"))
            pdf.ln(5)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 7, "Wins:", ln=True)
            pdf.set_font("Arial", "", 11)
            for win in summary.get("wins", []):
                pdf.cell(10)
                pdf.multi_cell(0, 7, sanitize(f"- {win}"))
            pdf.ln(5)
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 7, "Focus Areas:", ln=True)
            pdf.set_font("Arial", "", 11)
            for focus in summary.get("focus_areas", []):
                pdf.cell(10)
                pdf.multi_cell(0, 7, sanitize(f"- {focus}"))
        
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, "Note: This is a Windows/Dev fallback report. Deployment on ARM uses premium WeasyPrint layout.", ln=True)
        
        return bytes(pdf.output())

    def upload_to_s3(self, pdf_content: bytes, tenant_id: str) -> str:
        """Uploads to S3 and returns the S3 Key."""
        filename = f"reports/{tenant_id}_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.pdf"
        return s3_service.upload_file(pdf_content, filename, "application/pdf")

    def get_presigned_url(self, s3_key: str, expires_in: int = 3600) -> str:
        """Generates a pre-signed URL for an existing S3 Key."""
        return s3_service.get_presigned_url(s3_key, expires_in)

    def upload_and_presign(self, pdf_content: bytes, tenant_id: str) -> tuple[str, str]:
        """Uploads to S3 and returns (presigned_url, s3_key)."""
        s3_key = self.upload_to_s3(pdf_content, tenant_id)
        url = self.get_presigned_url(s3_key)
        return url, s3_key
