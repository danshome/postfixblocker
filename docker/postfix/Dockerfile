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
# Install base requirements first (portable across architectures)
COPY requirements-base.txt /tmp/requirements-base.txt
RUN pip install --no-cache-dir -r /tmp/requirements-base.txt

# Optionally install DB2 client libraries (ibm-db/ibm-db-sa). These packages
# do not provide wheels for all architectures; make this conditional so the
# Postgres-only image can build on arm64 (e.g., Apple Silicon) without errors.
ARG ENABLE_DB2=0
COPY requirements-db2.txt /tmp/requirements-db2.txt
RUN if [ "$ENABLE_DB2" = "1" ]; then pip install --no-cache-dir -r /tmp/requirements-db2.txt; fi

COPY app /opt/app
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /opt/app

EXPOSE 25 5000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
