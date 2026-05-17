FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libportaudio2 \
    portaudio19-dev \
    alsa-utils \
    pulseaudio-utils \
    netcat-openbsd \
    openssh-client \
    tor \
    xdotool \
    wmctrl \
    playerctl \
    brightnessctl \
    scrot \
    tesseract-ocr \
    tesseract-ocr-tur \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY gereksinimler.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r gereksinimler.txt \
    && python -m playwright install --with-deps chromium

COPY . .

RUN chmod +x baslat.sh kur.sh tani.py uzuv_stub_uret.py

CMD ["python", "tani.py"]
