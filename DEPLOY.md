# Render Deployment Guide — Question Paper Generator

## ⚠️ Cold Start Disclaimer

> **Render Free Tier services spin down after 15 minutes of inactivity.** The first request after idle will take **30–60 seconds**. PDF processing with OCR adds an additional **10–30 seconds** per page.

---

## 🔑 Getting Your Free Gemini API Key

1. Visit **[Google AI Studio](https://aistudio.google.com/app/apikey)**
2. Sign in with your Google account — **completely free**
3. Click **"Create API Key"** → Copy the key
4. No credit card needed, no trial expiration

### Free Tier Rate Limits

| Model | RPM | Best For |
|-------|-----|----------|
| `gemini-1.5-pro` (current) | 2 | High-quality question generation |
| `gemini-2.5-pro` | 2 | Even better quality |
| `gemini-flash-latest` | 15 | Faster generation, good quality |

---

## 🔄 Model Fallback Routing

The app currently uses `gemini-1.5-pro`. Recommended upgrade with fallback:

```python
# Suggested: Replace configure_api() in app.py
MODEL_CASCADE = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

def configure_api():
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not set.")
    genai.configure(api_key=GOOGLE_API_KEY)
    
    for model_name in MODEL_CASCADE:
        try:
            model = genai.GenerativeModel(model_name)
            return model, genai
        except Exception:
            continue
    return genai.GenerativeModel(MODEL_CASCADE[-1]), genai
```

---

## Environment Variables (Render Dashboard)

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | ✅ Yes | From [AI Studio](https://aistudio.google.com/app/apikey) |

---

## Deployment Steps

### 1. Create Render Web Service
1. [render.com/new](https://dashboard.render.com/new) → Connect GitHub
2. Environment: **Docker** → Instance Type: **Free**
3. Add `GOOGLE_API_KEY` in environment variables

### 2. System Dependencies
The Dockerfile installs `poppler-utils` and `tesseract-ocr` automatically:
```dockerfile
RUN apt-get install -y poppler-utils tesseract-ocr
```

### 3. Files
```
Dockerfile → python:3.10-slim + poppler + tesseract → pip install deps
start.sh   → gunicorn app:app --workers 1 --bind 0.0.0.0:$PORT --timeout 120
```

---

## Resource Limits

| Resource | Render Free Tier | This Project |
|----------|-----------------|--------------|
| RAM | 512 MB | ~200 MB (Flask + poppler + tesseract) |
| Storage | 1 GB | ~150 MB (system deps + code) |
| Bandwidth | 100 GB/month | Moderate (PDF uploads/downloads) |

> ⚠️ **Note:** Tesseract OCR and Poppler add ~100MB to the container. If RAM becomes an issue, consider switching from OCR to PyPDF2-only text extraction.
