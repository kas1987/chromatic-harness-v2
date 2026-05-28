FROM python:3.12-slim
WORKDIR /workspace
COPY . /workspace
RUN pip install --no-cache-dir pydantic fastapi uvicorn
CMD ["python", "-m", "http.server", "8787"]
