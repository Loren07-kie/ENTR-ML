FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-spa tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN tesseract --list-langs | grep -q spa && tesseract --list-langs | grep -q eng
COPY . .
RUN python tools/train.py && python tools/train_photo.py
RUN python tools/download_htr.py
ENV OMP_THREAD_LIMIT=1
CMD ["sh", "-c", "exec gunicorn --workers 1 --threads 4 --timeout 120 --bind 0.0.0.0:${PORT:-8000} app:app"]
