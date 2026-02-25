FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    systemd \
    iproute2 \
    procps \
    curl

RUN mkdir -p /run/systemd /run/lock /run/lock/subsys

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 2053

CMD ["python", "main.py"]
