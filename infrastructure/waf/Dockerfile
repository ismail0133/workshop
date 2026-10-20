# Edge reverse proxy. Pin the base image by digest once the build works:
#   docker pull nginxinc/nginx-unprivileged:1.27-alpine && docker inspect --format '{{index .RepoDigests 0}}' ...
FROM nginxinc/nginx-unprivileged:1.27-alpine

USER root
RUN apk add --no-cache openssl \
 && rm -f /etc/nginx/conf.d/default.conf \
 && mkdir -p /opt/waf /etc/nginx/snippets /var/log/resilience/waf \
 && chown -R 101:101 /var/log/resilience

COPY nginx.conf /etc/nginx/nginx.conf
COPY snippets/  /etc/nginx/snippets/
COPY blocklist.sh entrypoint.sh /opt/waf/

# tolerate files edited on Windows (CRLF)
RUN sed -i 's/\r$//' /etc/nginx/nginx.conf /etc/nginx/snippets/*.conf /opt/waf/*.sh \
 && chmod 755 /opt/waf/*.sh

USER 101
EXPOSE 8080 8443
ENTRYPOINT ["/opt/waf/entrypoint.sh"]
