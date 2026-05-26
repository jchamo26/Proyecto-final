FROM python:3.12-slim
WORKDIR /ml
COPY ./app /ml/app
COPY requirements.txt /ml/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
EXPOSE 8100
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
