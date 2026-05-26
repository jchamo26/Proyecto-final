FROM python:3.12-slim
WORKDIR /agent
COPY ./app /agent/app
COPY requirements.txt /agent/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
EXPOSE 8300
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8300"]
