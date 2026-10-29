import os
import tempfile
from unittest import mock

from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, override_settings

from utils import deploy


def _request(factory, method='post', staff=True):
    request = getattr(factory, method)('/system_update/')
    request.user = mock.Mock(is_staff=staff, is_active=True, is_authenticated=True)
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def _staff_request_post(factory, data):
    request = factory.post('/system_update/', data)
    request.user = mock.Mock(is_staff=True, is_active=True, is_authenticated=True)
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


class OsRunTest(SimpleTestCase):
    def test_comando_string_usa_shlex(self):
        with mock.patch('utils.deploy.subprocess.run') as run:
            run.return_value = mock.Mock(stdout=b'ok', stderr=b'', returncode=0)
            deploy.os_run('echo "a b"')
        self.assertEqual(run.call_args[0][0], ['echo', 'a b'])

    def test_codigo_diferente_de_zero_levanta(self):
        with mock.patch('utils.deploy.subprocess.run') as run:
            run.return_value = mock.Mock(stdout=b'', stderr=b'falhou', returncode=2)
            with self.assertRaises(ValidationError):
                deploy.os_run(['x'])

    def test_timeout_tem_mensagem_propria(self):
        import subprocess
        with mock.patch('utils.deploy.subprocess.run',
                        side_effect=subprocess.TimeoutExpired('x', 1)):
            with self.assertRaisesMessage(ValidationError, 'Timeout'):
                deploy.os_run(['x'], timeout=1)


class SystemUpdateViewTest(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = override_settings(BASE_DIR=self.tmp.name)
        patcher.enable()
        self.addCleanup(patcher.disable)

    @mock.patch('utils.deploy.os_run', return_value='ok')
    def test_get_nao_executa(self, run):
        response = deploy.system_update(_request(self.factory, 'get'))
        self.assertEqual(response.status_code, 200)
        run.assert_not_called()

    def test_nao_staff_e_negado(self):
        with mock.patch('utils.deploy.os_run') as run:
            response = deploy.system_update(_request(self.factory, staff=False))
        self.assertEqual(response.status_code, 302)
        run.assert_not_called()

    @mock.patch('utils.deploy.os_run', return_value='linha1\nlinha2')
    def test_post_invoca_script_e_monta_log(self, run):
        response = deploy.system_update(_request(self.factory))
        args, kwargs = run.call_args
        self.assertEqual(args[0], ['bash', 'deploy.sh'])
        self.assertEqual(kwargs['cwd'], self.tmp.name)
        self.assertIn('linha1<br/>linha2', response.content.decode())

    @mock.patch('utils.deploy.os_run', return_value='<script>x</script>')
    def test_saida_e_escapada(self, run):
        response = deploy.system_update(_request(self.factory))
        self.assertNotIn('<script>x', response.content.decode())

    @mock.patch('utils.deploy.os_run', side_effect=ValidationError('git falhou'))
    def test_falha_exibe_erro_e_libera_lock(self, run):
        response = deploy.system_update(_request(self.factory))
        self.assertIn('git falhou', response.content.decode())
        self.assertFalse(os.path.exists(deploy._lock_path()))

    @mock.patch('utils.deploy.os.name', 'posix')
    @mock.patch('utils.deploy.os_run', return_value='ok')
    def test_passa_project_dir_e_python_path(self, run):
        deploy.system_update(_request(self.factory))
        env = run.call_args[1]['env']
        self.assertEqual(env['PROJECT_DIR'], self.tmp.name)
        self.assertEqual(env['PYTHON_PATH'], deploy.sys.executable)

    @mock.patch('utils.deploy.os_run', return_value='ok')
    def test_credencial_vai_no_env_e_nao_aparece_no_log(self, run):
        request = _staff_request_post(self.factory, {'git_user': 'u', 'git_token': 'segredo123'})
        with mock.patch('utils.deploy.os_run', return_value='pull com segredo123 ok') as run:
            response = deploy.system_update_git(request)
        env = run.call_args[1]['env']
        self.assertEqual((env['GIT_USER'], env['GIT_TOKEN']), ('u', 'segredo123'))
        self.assertNotIn('segredo123', response.content.decode())

    @mock.patch('utils.deploy.os_run', return_value='ok')
    def test_system_update_ignora_credencial_do_post(self, run):
        request = _staff_request_post(self.factory, {'git_user': 'u', 'git_token': 'segredo123'})
        deploy.system_update(request)
        env = run.call_args[1]['env']
        self.assertNotEqual(env.get('GIT_TOKEN'), 'segredo123')

    @mock.patch('utils.deploy.os_run', return_value='ok')
    def test_system_update_git_exige_token(self, run):
        deploy.system_update_git(_staff_request_post(self.factory, {'git_user': 'u'}))
        run.assert_not_called()
        self.assertFalse(os.path.exists(deploy._lock_path()))

    def test_diagnostico_usa_check_e_nao_toma_lock(self):
        request = _staff_request_post(self.factory, {'action': 'check'})
        with mock.patch('utils.deploy.os_run', return_value='ok') as run:
            deploy.system_update(request)
        self.assertEqual(run.call_args[0][0], ['bash', 'deploy.sh', '--check'])
        self.assertFalse(os.path.exists(deploy._lock_path()))

    @override_settings(DEBUG=True)
    @mock.patch('utils.deploy.os_run', return_value='ok')
    def test_debug_pula_restart(self, run):
        deploy.system_update(_request(self.factory))
        self.assertEqual(run.call_args[1]['env']['SKIP_RESTART'], '1')

    @mock.patch('utils.deploy.os_run', return_value='ok')
    def test_deploy_concorrente_recusado(self, run):
        self.assertTrue(deploy._acquire_lock())
        self.addCleanup(deploy._release_lock)
        deploy.system_update(_request(self.factory))
        run.assert_not_called()
