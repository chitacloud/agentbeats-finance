FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server.py agent.py ./

EXPOSE 8080

# ENTRYPOINT required so --host/--port/--card-url args work
ENTRYPOINT ["python3", "server.py"]
CMD ["--host", "0.0.0.0", "--port", "8080"]
