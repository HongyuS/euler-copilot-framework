FROM hub.oepkgs.net/neocopilot/framework_base:0.9.6-x86-test

ENV PYTHONPATH=/app
ENV TIKTOKEN_CACHE_DIR=/app/assets/tiktoken

COPY --chmod=550 ./ /app/

CMD ["uv", "run", "--no-sync", "--no-dev", "apps/main.py"]
