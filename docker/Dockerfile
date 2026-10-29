# Ambiente de teste parecido com produção: supervisor + nginx + gunicorn
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor git bash curl \
       build-essential pkg-config default-libmysqlclient-dev libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Usuário que roda o gunicorn (como em produção)
RUN useradd --create-home --shell /bin/bash webapp

RUN python -m venv /opt/venv
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Configs
COPY docker/nginx.conf /etc/nginx/conf.d/twitsearch.conf
COPY docker/supervisord.conf /etc/supervisor/supervisord.conf
RUN rm -f /etc/nginx/sites-enabled/default /etc/nginx/conf.d/default.conf

# O checkout é montado em /app (git pull / sqlite do próprio projeto).
# Git: aceita o diretório montado e ignora diferença de modo de arquivo (Windows).
RUN git config --system --add safe.directory '*' \
    && git config --system core.fileMode false \
    && git config --system url."https://github.com/".insteadOf "git@github.com:" \
    && git config --system credential.helper '!f() { echo username=$GIT_USER; echo password=$GIT_TOKEN; }; f'

WORKDIR /app
EXPOSE 80
CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
