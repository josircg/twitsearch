#!/usr/bin/env bash
#
# deploy.sh — Deploy local do twitsearch
#
# Passos (no próprio servidor onde o Django roda):
#   0. identifica o branch corrente do checkout (é sempre o branch que será atualizado)
#   1. git pull --ff-only
#   2. pip install -r requirements.txt   (opcional, INSTALL_DEPS=1)
#   3. migrate --noinput
#   4. collectstatic --noinput
#   5. restart do serviço no supervisor (assíncrono, para a resposta HTTP sair antes)
#
# Aborta no primeiro erro e propaga o código de saída.
#
# Variáveis de ambiente:
#   PROJECT_DIR             raiz do projeto            (passado pelo Django; default: diretório do script)
#   PYTHON_PATH             executável Python do venv  (passado pelo Django; default: python3 do PATH)
#   SUPERVISOR_SERVICE      programa no supervisor     (sem ele o deploy roda mas não reinicia)
#   GIT_USER / GIT_TOKEN    credencial do pull (opcional; informada pela view)
#   --check                 apenas diagnostica o ambiente
#   DJANGO_SETTINGS_MODULE  settings dos commands      (default: twitsearch.local)
#   SKIP_RESTART            "1" não reinicia o serviço (DEBUG/dev)
#   INSTALL_DEPS            "1" roda pip install -r requirements.txt
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECT_DIR="${PROJECT_DIR:-$SCRIPT_DIR}"
PYTHON_PATH="${PYTHON_PATH:-}"
SUPERVISOR_SERVICE="${SUPERVISOR_SERVICE:-}"
SKIP_RESTART="${SKIP_RESTART:-0}"
INSTALL_DEPS="${INSTALL_DEPS:-0}"
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-twitsearch.local}"

# Sob o supervisor o HOME costuma vir vazio ou apontando para outro usuário (ex.: /root).
# Sem um HOME válido o git não acha ~/.gitconfig nem ~/.git-credentials e o pull falha com
# "unable to set up default path". Usa o diretório do usuário que roda o processo.
if [ -z "${HOME:-}" ] || [ ! -w "$HOME" ]; then
    USER_HOME="$(getent passwd "$(id -u)" 2>/dev/null | cut -d: -f6 || true)"
    [ -n "$USER_HOME" ] || USER_HOME="$(eval echo "~$(id -un)" 2>/dev/null || true)"
    if [ -n "$USER_HOME" ]; then
        export HOME="$USER_HOME"
    fi
fi
# Nunca pede usuário/senha no terminal (não há TTY): falha direto se faltar credencial.
export GIT_TERMINAL_PROMPT=0

# Executa git usando GIT_USER/GIT_TOKEN (informados pela view, só no ambiente deste processo)
# quando houver; senão usa a configuração normal do git do usuário.
git_auth() {
    if [ -n "${GIT_TOKEN:-}" ]; then
        git -c credential.helper= \
            -c 'credential.helper=!f() { echo "username=${GIT_USER:-oauth2}"; echo "password=${GIT_TOKEN}"; }; f' \
            "$@"
    else
        git "$@"
    fi
}

if [ -n "$PYTHON_PATH" ]; then
    PYTHON="$PYTHON_PATH"
else
    PYTHON="$(command -v python3 || command -v python)"
    echo "AVISO: PYTHON_PATH não definido; usando $PYTHON"
fi

cd "$PROJECT_DIR"

# --check: só diagnostica o ambiente (nada é alterado). Útil quando não há acesso ao servidor.
if [ "${1:-}" = "--check" ]; then
    echo "== Diagnóstico do ambiente =="
    echo "usuário: $(id -un)  HOME: ${HOME:-}"
    echo "PROJECT_DIR: $PROJECT_DIR"
    echo "PYTHON: $PYTHON ($("$PYTHON" --version 2>&1))"
    echo "DJANGO_SETTINGS_MODULE: $DJANGO_SETTINGS_MODULE"
    echo "SUPERVISOR_SERVICE: ${SUPERVISOR_SERVICE:-<não definido>}"
    echo "branch: $(git rev-parse --abbrev-ref HEAD 2>&1)"
    echo "commit: $(git log -1 --format='%h %ad %s' --date=short 2>&1)"
    echo "remote: $(git remote get-url origin 2>&1 | sed -E 's#//[^@/]*@#//#')"
    echo "alterações locais: $(git status --short 2>&1 | wc -l) arquivo(s)"
    echo "credential.helper: $(git config --show-origin --get-all credential.helper 2>&1 | tr '\n' ' ')"
    if [ -f "$HOME/.git-credentials" ]; then echo "~/.git-credentials: existe"; else echo "~/.git-credentials: não existe"; fi
    echo "token informado na tela: $([ -n "${GIT_TOKEN:-}" ] && echo sim || echo não)"
    if git_auth ls-remote --exit-code origin HEAD >/dev/null 2>&1; then
        echo "acesso ao remoto (git ls-remote): OK"
    else
        echo "acesso ao remoto (git ls-remote): FALHOU (sem credencial válida para este usuário)"
    fi
    if command -v supervisorctl >/dev/null 2>&1; then
        echo "supervisorctl status:"
        supervisorctl status 2>&1 | sed 's/^/  /' || true
    else
        echo "supervisorctl: não encontrado no PATH"
    fi
    exit 0
fi

if [ "$SKIP_RESTART" != "1" ] && [ -z "$SUPERVISOR_SERVICE" ]; then
    echo "AVISO: SUPERVISOR_SERVICE não definido; o serviço NÃO será reiniciado ao final"
    SKIP_RESTART=1
    NO_SERVICE=1
fi

echo "== Deploy iniciado em $(date '+%Y-%m-%d %H:%M:%S') =="
echo "PROJECT_DIR=$PROJECT_DIR"
echo "PYTHON=$PYTHON"
echo "DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"
echo "USER=$(id -un) HOME=${HOME:-}"

echo "== [0/5] branch corrente =="
echo "branch atual: $(git rev-parse --abbrev-ref HEAD)"

echo "== [1/5] git pull --ff-only =="
git_auth pull --ff-only

if [ "$INSTALL_DEPS" = "1" ]; then
    echo "== [2/5] pip install -r requirements.txt =="
    "$PYTHON" -m pip install -r requirements.txt
else
    echo "== [2/5] dependências: pulado (INSTALL_DEPS!=1) =="
fi

echo "== [3/5] migrate =="
"$PYTHON" manage.py migrate --noinput

echo "== [4/5] collectstatic =="
"$PYTHON" manage.py collectstatic --noinput

if [ "$SKIP_RESTART" = "1" ]; then
    echo "== [5/5] restart pulado =="
else
    echo "== [5/5] agendando restart assíncrono de '$SUPERVISOR_SERVICE' =="
    setsid bash -c "sleep 2 && supervisorctl restart '$SUPERVISOR_SERVICE'" \
        >>"$PROJECT_DIR/deploy-restart.log" 2>&1 < /dev/null &
    echo "restart agendado (erros em deploy-restart.log)"
fi

if [ "${NO_SERVICE:-0}" = "1" ]; then
    echo "== Deploy concluído, mas o serviço NÃO foi reiniciado (informe o serviço do supervisor) =="
else
    echo "== Deploy concluído com sucesso =="
fi
