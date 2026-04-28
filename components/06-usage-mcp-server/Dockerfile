FROM registry.access.redhat.com/ubi9/python-311:latest

LABEL name="usage-mcp-server-v2" \
      version="2.0.0" \
      description="Mobile Usage MCP Server V2 with PostgreSQL backend"

WORKDIR /app

COPY src/requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/server.py /app/

EXPOSE 8000

CMD ["python", "/app/server.py"]
