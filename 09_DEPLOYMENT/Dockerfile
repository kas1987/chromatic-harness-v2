FROM python:3.12-slim
WORKDIR /workspace
COPY requirements.txt /workspace/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . /workspace
ENV PYTHONPATH=/workspace/02_RUNTIME:/workspace
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8787", "--app-dir", "/workspace/02_RUNTIME"]
