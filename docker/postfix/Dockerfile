FROM rockylinux/rockylinux:9.5

# Base OS packages (RHEL/CentOS Stream 9)
RUN dnf -y update && \
    dnf -y install dnf-plugins-core && \
    dnf -y install epel-release && \
    (dnf config-manager --set-enabled crb || true) && \
    dnf -y install postfix procps-ng postfix-pcre rsyslog supervisor python3 python3-pip which && \
    dnf -y install python3-devel gcc gcc-c++ make openssl-devel libffi-devel && \
    dnf clean all && rm -rf /var/cache/dnf && \
    postconf -F 'smtp/inet/chroot=n'

RUN sed -i 's/SysSock.Use="off"/SysSock.Use="on"/' /etc/rsyslog.conf && \
    sed -i 's/^module(load="imjournal"/#module(load="imjournal"/' /etc/rsyslog.conf && \
    touch /var/log/maillog /var/log/messages /var/log/secure /var/log/cron /var/log/boot.log

# Postfix setup
COPY docker/postfix/main.cf /etc/postfix/main.cf

# Python deps
# Install base requirements first (portable across architectures)
COPY requirements-base.txt /tmp/requirements-base.txt
RUN pip3 install --no-cache-dir -r /tmp/requirements-base.txt

# Optionally install DB2 client libraries (ibm-db/ibm-db-sa). These packages
# do not provide wheels for all architectures; make this conditional so the
# Postgres-only image can build on arm64 (e.g., Apple Silicon) without errors.
ARG ENABLE_DB2=0
COPY requirements-db2.txt /tmp/requirements-db2.txt
# Install DB2 Python drivers only on x86_64 where wheels/support are typically available.
RUN ARCH=$(uname -m); \
    if [ "$ENABLE_DB2" = "1" ] && [ "$ARCH" = "x86_64" ]; then \
        echo "Installing DB2 Python deps on $ARCH" && \
        pip3 install --no-cache-dir -r /tmp/requirements-db2.txt; \
    else \
        echo "Skipping DB2 Python deps (ENABLE_DB2=$ENABLE_DB2, ARCH=$ARCH)"; \
    fi

COPY postfix_blocker /opt/postfix_blocker
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
# Ensure mail.* is logged to /var/log/maillog regardless of severity
COPY docker/postfix/rsyslog-postfix.conf /etc/rsyslog.d/99-postfix.conf

RUN mkdir -p /var/log/postfix-blocker /var/run/postfix-blocker

WORKDIR /opt

EXPOSE 25 5000

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
