import hashlib
import hmac

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.hash_projeto import hash_projeto, indice_valido, token_projeto
from core.models import Projeto, Rede
from telegram.models import DS_TELEGRAM
from twitsearch.test_credentials import CHAVE_HASH, CHAVE_HASH_ALTERNATIVA, SENHA_USUARIO

GESTAO = 'https://gestao.exemplo.br'


@override_settings(PROJETO_HASH_KEY=CHAVE_HASH)
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
        with override_settings(PROJETO_HASH_KEY=CHAVE_HASH_ALTERNATIVA):
            self.assertNotEqual(base, hash_projeto(7, 'telegram'))

    @staticmethod
    def esperado(mensagem):
        return hmac.new(CHAVE_HASH.encode(), mensagem.encode(), hashlib.sha256).hexdigest()[:32]

    def test_formula_sem_indice_e_a_de_antes(self):
        # mesma mensagem que o Gestão (utils/hash_projeto.py) valida; links antigos continuam válidos
        self.assertEqual(hash_projeto(100, 'telegram'), self.esperado('projeto:100:telegram'))
        self.assertEqual(hash_projeto(100, 'telegram', ''), self.esperado('projeto:100:telegram'))

    def test_formula_com_indice(self):
        self.assertEqual(hash_projeto(100, 'telegram', 'capitu'), self.esperado('projeto:100:telegram:capitu'))
        self.assertEqual(token_projeto(100, 'telegram', 'capitu'),
                         f'100-{self.esperado("projeto:100:telegram:capitu")}')

    def test_muda_com_indice(self):
        base = hash_projeto(7, 'telegram', 'capitu')
        self.assertNotEqual(base, hash_projeto(7, 'telegram'))
        self.assertNotEqual(base, hash_projeto(7, 'telegram', 'capitu2'))


class IndiceValidoTests(SimpleTestCase):

    def test_aceita(self):
        for indice in ('capitu', 'vtrack-telegram-test', 'a', 'a1-b2', 'a' * 20):
            with self.subTest(indice=indice):
                self.assertTrue(indice_valido(indice))

    def test_recusa(self):
        for indice in ('', None, 'Capitu', '1abc', '-abc', 'a*', 'a,b', 'a b', 'a_b', 'a' * 21, 'capitu\n'):
            with self.subTest(indice=indice):
                self.assertFalse(indice_valido(indice))


class UrlResultadoTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.telegram = Rede.objects.create(nome='Telegram')
        cls.twitter = Rede.objects.create(nome='Twitter')
        cls.user = User.objects.create_user('ana', password=SENHA_USUARIO)

    def projeto(self, rede=None, prefix=''):
        projeto = Projeto.objects.create(nome='P', objetivo='x', usuario=self.user, prefix=prefix)
        projeto.redes.add(rede or self.telegram)
        return projeto

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY=CHAVE_HASH)
    def test_url_completa_com_ds_telegram(self):
        projeto = self.projeto()
        url = projeto.url_resultado
        self.assertEqual(DS_TELEGRAM, 'telegram')
        self.assertEqual(url, f'{GESTAO}/dashboard?hash={token_projeto(projeto.pk, "telegram")}&ds=telegram')
        self.assertRegex(url, rf'hash={projeto.pk}-[0-9a-f]{{32}}&ds=telegram$')

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY=CHAVE_HASH)
    def test_prefixo_vai_no_idx_e_no_hash(self):
        projeto = self.projeto(prefix='capitu')
        self.assertEqual(
            projeto.url_resultado,
            f'{GESTAO}/dashboard?hash={token_projeto(projeto.pk, "telegram", "capitu")}&ds=telegram&idx=capitu')

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY=CHAVE_HASH)
    def test_trocar_o_prefixo_muda_o_link(self):
        projeto = self.projeto(prefix='telegram')
        antes = projeto.url_resultado
        projeto.prefix = 'capitu'
        projeto.save(update_fields=['prefix'])
        depois = projeto.url_resultado
        self.assertNotEqual(antes, depois)
        self.assertIn('idx=telegram', antes)
        self.assertIn('idx=capitu', depois)

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY=CHAVE_HASH)
    def test_prefixo_fora_da_regra_usa_o_link_sem_idx(self):
        # prefixos antigos, gravados antes do clean_prefix, ou começando por '-'
        for prefix in ('Capitu', 'vtrack*', '-capitu', 'a' * 21):
            with self.subTest(prefix=prefix):
                projeto = self.projeto(prefix=prefix)
                self.assertEqual(projeto.url_resultado,
                                 f'{GESTAO}/dashboard?hash={token_projeto(projeto.pk, "telegram")}&ds=telegram')

    @override_settings(GESTAO_URL=GESTAO + '/', PROJETO_HASH_KEY=CHAVE_HASH)
    def test_barra_final_do_gestao_url_e_ignorada(self):
        self.assertTrue(self.projeto().url_resultado.startswith(f'{GESTAO}/dashboard?'))

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY=CHAVE_HASH)
    def test_none_para_projeto_sem_rede_telegram(self):
        self.assertIsNone(self.projeto(rede=self.twitter, prefix='twitter').url_resultado)

    @override_settings(GESTAO_URL='', PROJETO_HASH_KEY=CHAVE_HASH)
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
        cls.user = User.objects.create_user('ana', password=SENHA_USUARIO)

    def test_anonimo_no_painel_vai_para_o_login(self):
        resposta = self.client.get('/painel/')
        self.assertRedirects(resposta, '/login/?next=/painel/')

    def test_get_login_usa_o_template_proprio(self):
        resposta = self.client.get('/login/')
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, 'login.html')

    def test_login_valido_vai_para_o_painel(self):
        resposta = self.client.post('/login/', {'username': 'ana', 'password': SENHA_USUARIO})
        self.assertRedirects(resposta, '/painel/', fetch_redirect_response=False)

    def test_login_valido_respeita_o_next(self):
        resposta = self.client.post('/login/', {
            'username': 'ana', 'password': SENHA_USUARIO, 'next': '/telegram/listas/',
        })
        self.assertRedirects(resposta, '/telegram/listas/', fetch_redirect_response=False)

    def test_credenciais_invalidas_mostram_erro(self):
        resposta = self.client.post('/login/', {'username': 'ana', 'password': SENHA_USUARIO + '-errada'})
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
        User.objects.create_user('staff', password=SENHA_USUARIO, is_staff=True)
        resposta = self.client.post('/login/', {'username': 'staff', 'password': SENHA_USUARIO, 'next': '/admin/'})
        self.assertRedirects(resposta, '/admin/', fetch_redirect_response=False)

    def test_admin_sem_staff_vai_para_o_painel_sem_loop(self):
        self.client.force_login(self.user)
        resposta = self.client.get('/admin/', follow=True)
        self.assertRedirects(resposta, '/painel/')
        self.assertContains(resposta, 'Sua conta não tem acesso à administração.')

    def test_pagina_de_redefinir_senha_abre(self):
        resposta = self.client.get(reverse('password_reset'))
        self.assertEqual(resposta.status_code, 200)
