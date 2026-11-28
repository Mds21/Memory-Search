FROM python:3.12-slim
# OCR (Tesseract + Indian languages), scanned PDFs (Poppler), video (FFmpeg); libgl/glib for RapidOCR's OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg poppler-utils tesseract-ocr tesseract-ocr-eng tesseract-ocr-hin \
        tesseract-ocr-mar tesseract-ocr-tam tesseract-ocr-spa libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Image understanding (multilingual CLIP). CPU-only PyTorch; works on x86 and ARM (Oracle Ampere). IMAGE_SEARCH=0 skips it.
ARG IMAGE_SEARCH=1
RUN if [ "$IMAGE_SEARCH" = "1" ]; then \
      pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
      pip install --no-cache-dir open_clip_torch transformers; fi
COPY app ./app
# HF_HOME on the data volume: the 1.7 GB image model downloads once and survives rebuilds
ENV DATA_DIR=/data DATABASE_URL=sqlite:////data/smriti.db HF_HOME=/data/hf PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
