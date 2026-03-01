import os
import io
import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import matplotlib
matplotlib.use('Agg') 
from fpdf import FPDF
import boto3
from botocore.config import Config
from app.core.config import settings

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

    def generate_glucose_chart(self, df_entries) -> io.BytesIO:
        """Generates a glucose trend chart and returns as BytesIO."""
        plt.figure(figsize=(10, 5))
        
        if not df_entries.empty:
            # Convert unix ms to datetime
            df_entries['datetime'] = pd.to_datetime(df_entries['date'], unit='ms')
            plt.plot(df_entries['datetime'], df_entries['sgv'], color='#2196F3', linewidth=1.5, label='Glucose (mg/dL)')
            
            # Add target range shading (70-180)
            plt.axhspan(70, 180, color='#4CAF50', alpha=0.1, label='Target Range')
            
            # Formatting
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
            plt.xticks(rotation=45)
            plt.ylabel('mg/dL')
            plt.title('Glucose Trend')
            plt.grid(True, linestyle='--', alpha=0.3)
            plt.legend()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close()
        return buf

    def create_pdf(self, report_data: dict, user_info: dict) -> bytes:
        """Assembles the PDF using fpdf2."""
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("Arial", 'B', 20)
        pdf.set_text_color(33, 150, 243)
        pdf.cell(0, 15, "OneTwenty User Report", ln=True, align='C')
        
        pdf.set_font("Arial", '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, f"Generated on: {report_data['generation_date']}", ln=True, align='C')
        pdf.ln(10)

        # User Info
        pdf.set_font("Arial", 'B', 12)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 7, f"Name: {user_info.get('name', 'N/A')}", ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 7, f"Email: {user_info.get('email', 'N/A')}", ln=True)
        pdf.cell(0, 7, f"Report Period: {report_data['start_date']} to {report_data['end_date']}", ln=True)
        pdf.ln(10)

        # 1. Summary Section
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "1. Summary", ln=True)
        pdf.set_font("Arial", '', 11)
        
        metrics = report_data['metrics']
        pdf.cell(0, 7, f" - Average Glucose: {metrics['avg_glucose']} mg/dL", ln=True)
        pdf.cell(0, 7, f" - Time In Range (70-180): {metrics['tir_percent']}%", ln=True)
        pdf.cell(0, 7, f" - Time Below Range (<70): {metrics['tbr_percent']}%", ln=True)
        pdf.cell(0, 7, f" - Time Above Range (>180): {metrics['tar_percent']}%", ln=True)
        pdf.cell(0, 7, f" - Estimated HbA1c: {metrics['estimated_hba1c']}%", ln=True)
        pdf.ln(5)

        # 2. Daily Glucose Chart
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "2. Glucose Patterns", ln=True)
        
        chart_buf = self.generate_glucose_chart(report_data['df_entries'])
        # Temp save chart to add to PDF
        with open("temp_chart.png", "wb") as f:
            f.write(chart_buf.getbuffer())
        
        pdf.image("temp_chart.png", x=10, y=pdf.get_y(), w=190)
        pdf.set_y(pdf.get_y() + 100)
        os.remove("temp_chart.png")

        # 2.2 Weekly Trends
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "2.2 Trends", ln=True)
        pdf.set_font("Arial", '', 11)
        patterns = report_data['patterns']
        pdf.cell(0, 7, f" - Morning average (8-10 AM): {patterns['morning_spike']} mg/dL", ln=True)
        pdf.cell(0, 7, f" - Afternoon average (2-4 PM): {patterns['afternoon_dip']} mg/dL", ln=True)
        pdf.cell(0, 7, f" - Evening average (8-10 PM): {patterns['evening_rise']} mg/dL", ln=True)

        # 3. Activity & Eating
        pdf.add_page()
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "3. Exercise & Eating", ln=True)
        
        ex = report_data['exercise']
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Exercise Activity", ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 7, f" - Total Sessions: {ex['total_sessions']}", ln=True)
        pdf.cell(0, 7, f" - Average Duration: {ex['avg_duration']} min", ln=True)
        pdf.cell(0, 7, f" - Impact: Avg drop of {ex['avg_ex_drop']} mg/dL", ln=True)
        
        pdf.ln(5)
        eat = report_data['eating']
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Eating Behavior", ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 7, f" - Meals Logged: {eat['meals_logged']}", ln=True)
        pdf.cell(0, 7, f" - Avg Carbs: {eat['avg_carbs']} g", ln=True)
        pdf.cell(0, 7, f" - Common Foods: {eat['common_foods']}", ln=True)

        # Footer
        pdf.set_y(-20)
        pdf.set_font("Arial", 'I', 8)
        pdf.set_text_color(150, 150, 150)
        pdf.cell(0, 10, f"Page {pdf.page_no()} | Generated by OneTwenty | Consult your provider for medical advice.", align='C')

        return pdf.output()

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
