FROM python:3.10-slim

WORKDIR /app

# Install system deps for ta-lib C library
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib && ./configure --prefix=/usr && make && make install \
    && cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz \
    && apt-get purge -y --auto-remove build-essential wget \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/
COPY db/ ./db/
COPY strategies/ ./strategies/
COPY tg/ ./tg/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
