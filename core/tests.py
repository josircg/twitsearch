from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.hash_projeto import hash_projeto, token_projeto
from core.models import Projeto, Rede
from telegram.models import DS_TELEGRAM

GESTAO = 'https://gestao.exemplo.br'


@override_settings(PROJETO_HASH_KEY='chave-a')
class HashProjetoTests(SimpleTestCase):

    def test_formato_do_token(self):
        self.assertRegex(token_projeto(7, 'telegram'), r'^7-[0-9a-f]{32}$')

    def test_token_estavel(self):
        self.assertEqual(token_projeto(7, 'telegram'), token_projeto(7, 'telegram'))
        self.assertEqual(token_projeto(7, 'telegram'), f'7-{hash_projeto(7, "telegram")}')

    def test_muda_com_ds_projeto_ou_chave(self):
        base = hash_projeto(7, 'telegram')
        self.assertNotEqual(base, hash_projeto(7, 'twitter'))
        self.assertNotEqual(base, hash_projeto(8, 'telegram'))
        with override_settings(PROJETO_HASH_KEY='chave-b'):
            self.assertNotEqual(base, hash_projeto(7, 'telegram'))


class UrlResultadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.telegram = Rede.objects.create(nome='Telegram')
        cls.twitter = Rede.objects.create(nome='Twitter')
        cls.user = User.objects.create_user('ana', password='x')

    def projeto(self, rede=None, prefix=''):
        projeto = Projeto.objects.create(nome='P', objetivo='x', usuario=self.user, prefix=prefix)
        projeto.redes.add(rede or self.telegram)
        return projeto

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='chave-a')
    def test_url_completa_com_ds_telegram(self):
        projeto = self.projeto()
        url = projeto.url_resultado
        self.assertEqual(DS_TELEGRAM, 'telegram')
        self.assertEqual(url, f'{GESTAO}/dashboard?hash={token_projeto(projeto.pk, "telegram")}&ds=telegram')
        self.assertRegex(url, rf'hash={projeto.pk}-[0-9a-f]{{32}}&ds=telegram$')

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='chave-a')
    def test_prefixo_nao_altera_o_link(self):
        projeto = self.projeto(prefix='vtrack-telegram-test')
        self.assertEqual(projeto.url_resultado,
                         f'{GESTAO}/dashboard?hash={token_projeto(projeto.pk, "telegram")}&ds=telegram')

    @override_settings(GESTAO_URL=GESTAO + '/', PROJETO_HASH_KEY='chave-a')
    def test_barra_final_do_gestao_url_e_ignorada(self):
        self.assertTrue(self.projeto().url_resultado.startswith(f'{GESTAO}/dashboard?'))

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='chave-a')
    def test_none_para_projeto_sem_rede_telegram(self):
        self.assertIsNone(self.projeto(rede=self.twitter, prefix='twitter').url_resultado)

    @override_settings(GESTAO_URL='', PROJETO_HASH_KEY='chave-a')
    def test_none_sem_gestao_url(self):
        self.assertIsNone(self.projeto().url_resultado)

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='')
    def test_none_sem_chave(self):
        self.assertIsNone(self.projeto().url_resultado)

    def test_none_quando_settings_nao_define_as_chaves(self):
        # o local.py não é versionado e pode não ter GESTAO_URL/PROJETO_HASH_KEY
        with override_settings():
            for nome in ('GESTAO_URL', 'PROJETO_HASH_KEY'):
                if hasattr(settings, nome):
                    delattr(settings, nome)
            self.assertIsNone(self.projeto().url_resultado)


class LoginTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('ana', password='segredo-123')

    def test_anonimo_no_painel_vai_para_o_login(self):
        resposta = self.client.get('/painel/')
        self.assertRedirects(resposta, '/login/?next=/painel/')

    def test_get_login_usa_o_template_proprio(self):
        resposta = self.client.get('/login/')
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'login.html')

    def test_login_valido_vai_para_o_painel(self):
        resposta = self.client.post('/login/', {'username': 'ana', 'password': 'segredo-123'})
        self.assertRedirects(resposta, '/painel/', fetch_redirect_response=False)

    def test_login_valido_respeita_o_next(self):
        resposta = self.client.post('/login/', {
            'username': 'ana', 'password': 'segredo-123', 'next': '/telegram/listas/',
        })
        self.assertRedirects(resposta, '/telegram/listas/', fetch_redirect_response=False)

    def test_credenciais_invalidas_mostram_erro(self):
        resposta = self.client.post('/login/', {'username': 'ana', 'password': 'errada'})
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.context['form'].non_field_errors())

    def test_autenticado_no_login_vai_para_o_painel(self):
        self.client.force_login(self.user)
        resposta = self.client.get('/login/')
        self.assertRedirects(resposta, '/painel/', fetch_redirect_response=False)

    def test_admin_anonimo_vai_para_o_login_proprio(self):
        resposta = self.client.get('/admin/', follow=True)
        self.assertRedirects(resposta, '/login/?next=/admin/')
        self.assertTemplateUsed(resposta, 'login.html')

    def test_login_pelo_admin_volta_para_o_admin(self):
        User.objects.create_user('staff', password='segredo-123', is_staff=True)
        resposta = self.client.post('/login/', {'username': 'staff', 'password': 'segredo-123', 'next': '/admin/'})
        self.assertRedirects(resposta, '/admin/', fetch_redirect_response=False)

    def test_admin_sem_staff_vai_para_o_painel_sem_loop(self):
        self.client.force_login(self.user)
        resposta = self.client.get('/admin/', follow=True)
        self.assertRedirects(resposta, '/painel/')
        self.assertContains(resposta, 'Sua conta não tem acesso à administração.')

    def test_pagina_de_redefinir_senha_abre(self):
        resposta = self.client.get(reverse('password_reset'))
        self.assertEqual(resposta.status_code, 200)
