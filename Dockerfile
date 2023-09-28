FROM python:3.11-slim
RUN DEBIAN_FRONTEND=noninteractive apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/delaere/Note-Station-to-markdown.git
WORKDIR Note-Station-to-markdown
RUN pip install pandoc pyyaml pytz requests
RUN git checkout paperless
RUN mkdir data
ENTRYPOINT [ "python", "./migrate.py" ]
