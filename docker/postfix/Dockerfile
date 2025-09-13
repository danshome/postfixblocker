FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends postfix postfix-pcre supervisor rsyslog && \
    rm -rf /var/lib/apt/lists/* &&  \
    # Use syslog for logging (rsyslog) and disable smtpd chroot in containers
    postconf -X maillog_file && \
    postconf -F 'smtp/inet/chroot=n'

# Postfix setup
COPY docker/postfix/main.cf /etc/postfix/main.cf

# Python deps
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /opt/app
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /opt/app

EXPOSE 25 5000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
