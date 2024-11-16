FROM ubuntu:latest
LABEL authors="apple"

# Set up timezone to avoid prompts during installation
ENV TZ=UTC
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install Python and required system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create and activate virtual environment
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Create empty database
RUN python3 -c "from app import init_db; init_db()"

EXPOSE 6060

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
