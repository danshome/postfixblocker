FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends postfix supervisor && \
    rm -rf /var/lib/apt/lists/*

# Postfix setup
RUN postconf -e 'maillog_file = /dev/stdout'
COPY docker/postfix/main.cf /etc/postfix/main.cf

# Python deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /opt/app
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /opt/app

EXPOSE 25 5000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
