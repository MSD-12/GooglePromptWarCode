FROM python:3.11-slim
WORKDIR /app

# Streamlit requires these system level dependencies occasionally
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the app source code
COPY . .

# Set cloud run port environment variable
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK CMD curl --fail http://localhost:8080/_stcore/health

# Run streamlit
CMD ["python", "-m", "streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
