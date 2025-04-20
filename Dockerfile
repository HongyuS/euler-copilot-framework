FROM hub.oepkgs.net/neocopilot/framework-baseimg:dev

USER root
RUN sed -i 's/umask 002/umask 027/g' /etc/bashrc && \
    sed -i 's/umask 022/umask 027/g' /etc/bashrc && \
    yum remove -y gdb-gdbserver

USER eulercopilot
COPY --chown=1001:1001 --chmod=550 ./ /app/

ENV PYTHONPATH=/app
ENV TIKTOKEN_CACHE_DIR=/app/assets/tiktoken

CMD ["uv", "run", "--no-sync", "--no-dev", "apps/main.py"]
