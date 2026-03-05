FROM python:3.10-slim

WORKDIR /app

# Install system dependencies for pdf2image (poppler) and pytesseract (tesseract-ocr)
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir flask google-generativeai Werkzeug requests \
    pdf2image pytesseract PyPDF2 pandas fpdf markdown pdfkit beautifulsoup4 gunicorn

COPY . .

# Create required directories
RUN mkdir -p uploads temp_outputs static/js

EXPOSE 8000

CMD ["sh", "start.sh"]
