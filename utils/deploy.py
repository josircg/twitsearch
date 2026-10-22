import os
import shlex
import sys
import subprocess

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.utils.html import escape
from django.views.decorators.http import require_http_methods

# Menor que o timeout do gunicorn (-t120) e do nginx (proxy_read_timeout 120)
DEPLOY_TIMEOUT = 100
LOCK_FILENAME = '.deploy.lock'


def os_run(command, halt=True, timeout=None, cwd=None, env=None):
    """
    Executa um comando no SO e retorna o stdout.
    command: lista ou string; halt: True levanta ValidationError em falha;
    timeout: segundos; cwd: diretório; env: dict de variáveis (None = atual).
    """
    stderr = None
    out = ''
    try:
        if not isinstance(command, list):
            command = shlex.split(command)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=timeout, cwd=cwd, env=env)
        if result.stdout:
            out += '%s\n' % result.stdout.decode('utf-8', errors='replace')
        if result.returncode != 0:
            stderr = '%s\n Code:(%d)\n' % (result.stderr.decode('utf-8', errors='replace'), result.returncode)
    except subprocess.TimeoutExpired:
        stderr = 'Timeout: o comando excedeu %s segundos\n' % timeout
    except Exception as err:
        stderr = 'Error: {0}\n'.format(err)

    if stderr:
        if halt:
            raise ValidationError(stderr)
        out += stderr
    return out


def _lock_path():
    return os.path.join(str(settings.BASE_DIR), LOCK_FILENAME)


def _acquire_lock():
    """Cria o lock de forma atômica. Retorna False se já existe um deploy em curso."""
    path = _lock_path()
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            import time
            if time.time() - os.path.getmtime(path) > DEPLOY_TIMEOUT * 2:
                os.remove(path)  # lock obsoleto
                return _acquire_lock()
        except OSError:
            pass
        return False
    os.close(fd)
    return True


def _release_lock():
    try:
        os.remove(_lock_path())
    except OSError:
        pass


def _run_deploy_script(check=False, git_user='', git_token=''):
    """
    Invoca deploy.sh na raiz do projeto. Levanta ValidationError em falha.
    check=True só diagnostica o ambiente. git_user/git_token são opcionais
    e valem apenas para este processo (nada é gravado em disco).
    """
    base_dir = str(settings.BASE_DIR)
    env = os.environ.copy()
    # O Django informa ao script a raiz do projeto e o Python do venv em execução,
    # sem depender de configuração no supervisor. No Windows (bash/WSL) os caminhos
    # não são traduzidos, então o script usa seus defaults.
    if os.name != 'nt':
        env['PROJECT_DIR'] = base_dir
        env['PYTHON_PATH'] = sys.executable
    if settings.DEBUG:
        env['SKIP_RESTART'] = '1'
    if git_token:
        env['GIT_USER'] = git_user or 'oauth2'
        env['GIT_TOKEN'] = git_token
    command = ['bash', 'deploy.sh']
    if check:
        command.append('--check')
    # Caminho relativo + cwd: evita passar caminho absoluto do Windows ao bash (WSL)
    return os_run(command, cwd=base_dir, env=env, timeout=DEPLOY_TIMEOUT)


def _format_log(text, secret=''):
    if secret:
        text = text.replace(secret, '***')
    return escape(text).replace('\n', '<br/>')


def _handle_update(request, ask_git):
    """
    Fluxo comum das duas rotas. ask_git=True exige usuário/token do git informados na tela;
    ask_git=False não lê nada do formulário e usa a credencial já configurada no servidor.
    """
    log = ''
    if request.method == 'POST':
        check = request.POST.get('action') == 'check'
        user = token = ''
        if ask_git:
            user = request.POST.get('git_user', '').strip()
            token = request.POST.get('git_token', '').strip()
        # O diagnóstico não altera nada, então não precisa do lock.
        if ask_git and not check and not token:
            messages.error(request, 'Informe o token do git.')
        elif not check and not _acquire_lock():
            messages.error(request, 'Já existe um deploy em andamento.')
        else:
            try:
                log = _format_log(_run_deploy_script(check=check, git_user=user, git_token=token), token)
                messages.success(request, 'Diagnóstico concluído' if check else 'Update realizado com sucesso')
            except Exception as e:
                log = _format_log(f'{e}', token)
                messages.error(request, 'Erro durante o diagnóstico.' if check
                               else 'Erro durante o deploy. Verifique o log abaixo.')
            finally:
                if not check:
                    _release_lock()
    return render(request, 'deploy.html', {'result': log, 'ask_git': ask_git, 'titulo': 'Atualizar sistema'})


@staff_member_required
@require_http_methods(['GET', 'POST'])
def system_update(request):
    """Atualiza o sistema com a credencial git já configurada no servidor (não pede nada)."""
    return _handle_update(request, ask_git=False)


@staff_member_required
@require_http_methods(['GET', 'POST'])
def system_update_git(request):
    """Atualiza o sistema pedindo usuário/token do git (valem só para esta execução)."""
    return _handle_update(request, ask_git=True)
