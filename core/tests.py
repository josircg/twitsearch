from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings

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
