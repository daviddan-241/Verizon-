FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Create writable dir for seen tokens DB
RUN mkdir -p /data
ENV SEEN_DB_FILE=/data/seen_tokens.json
EXPOSE 10000
CMD ["python", "bot.py"]
