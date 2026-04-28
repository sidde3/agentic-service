FROM registry.access.redhat.com/ubi9/python-311:latest

LABEL name="helloworld-mcp-server" \
      version="1.0.0" \
      description="Simple Hello World MCP server for testing"

WORKDIR /app

COPY src/requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/server.py /app/

EXPOSE 8000

CMD ["python", "/app/server.py"]
