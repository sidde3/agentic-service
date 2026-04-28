FROM registry.access.redhat.com/ubi9/python-311:latest

LABEL name="router-service" \
      version="1.0.0" \
      description="Intent classifier router: BERT classification, Redis sessions, Postgres archival"

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY src/router/ /app/src/router/

USER 0
RUN chmod -R g=u /app
USER 1001

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "src.router.router:app", "--host", "0.0.0.0", "--port", "8000"]
