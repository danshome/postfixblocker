FROM rockylinux/rockylinux:9.5

# Base OS packages (RHEL/CentOS Stream 9)
RUN [ ! -f /usr/sbin/init ] && dnf -y install systemd;
RUN ([ -d /lib/systemd/system/sysinit.target.wants ] && cd /lib/systemd/system/sysinit.target.wants/ && for i in *; do [ $i == \
systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;

RUN dnf -y update && \
    dnf -y install dnf-plugins-core && \
    dnf -y install epel-release && \
    (dnf config-manager --set-enabled crb || true) && \
    dnf -y install postfix procps-ng postfix-pcre rsyslog supervisor python3 python3-pip which && \
    dnf -y install python3-devel gcc gcc-c++ make openssl-devel libffi-devel && \
    dnf -y upgrade && \
    dnf clean all && rm -rf /var/cache/dnf && \
    postconf -F 'smtp/inet/chroot=n'

#RUN sed -i 's/SysSock.Use="off"/SysSock.Use="on"/' /etc/rsyslog.conf && \
#    sed -i 's/^module(load="imjournal"/#module(load="imjournal"/' /etc/rsyslog.conf && \
#    touch /var/log/maillog /var/log/messages /var/log/secure /var/log/cron /var/log/boot.log

# Postfix setup
COPY docker/postfix/main.cf /etc/postfix/main.cf
COPY docker/postfix/rsyslog-postfix.conf /etc/rsyslog.d/99-postfix.conf

WORKDIR /opt

EXPOSE 25 5000

VOLUME [ "/sys/fs/cgroup" ]
CMD ["/usr/sbin/init"]