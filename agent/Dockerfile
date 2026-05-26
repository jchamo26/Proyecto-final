FROM python:3.12-slim
WORKDIR /agent

RUN apt-get update && apt-get install -y --no-install-recommends \
	gcc \
	g++ \
	libgomp1 \
	poppler-utils \
	&& rm -rf /var/lib/apt/lists/*

COPY . /agent
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt
EXPOSE 8300
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8300"]
