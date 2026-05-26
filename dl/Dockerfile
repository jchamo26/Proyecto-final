FROM python:3.12-slim
WORKDIR /dl
COPY ./app /dl/app
COPY requirements.txt /dl/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
EXPOSE 8200
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]
