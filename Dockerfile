# Dockerfile (put in repo root)
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# system deps for opencv, ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsm6 libxext6 build-essential git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/Hiveup

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /workspace/Hiveup 

CMD ["python", "app.py", "--mode", "cli"]

