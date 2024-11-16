FROM ubuntu:latest
LABEL authors="apple"

ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    libcairo2-dev \
    pkg-config \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -c "from app import init_db; init_db()"

EXPOSE 9090

CMD ["gunicorn", "--bind", "0.0.0.0:9090", "app:app"]
