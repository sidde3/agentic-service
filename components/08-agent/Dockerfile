FROM registry.access.redhat.com/ubi9/python-311:latest

LABEL name="agent-service" \
      version="2.0.0" \
      description="LlamaStack-based agent for mobile plan recommendations"

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/agent/  /app/src/agent/

USER 0
RUN chmod -R g=u /app
USER 1001

ENV PYTHONPATH=/app
EXPOSE 8080

CMD ["python", "-m", "uvicorn", "src.agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
