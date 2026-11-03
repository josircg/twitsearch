import re

from django.conf import settings
from django.test import SimpleTestCase, override_settings

from core.hash_projeto import hash_projeto, token_projeto
from core.models import Projeto

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


class UrlResultadoTests(SimpleTestCase):

    def projeto(self, prefix='telegram'):
        return Projeto(pk=7, nome='P', prefix=prefix)

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='chave-a')
    def test_url_completa(self):
        url = self.projeto().url_resultado
        self.assertEqual(url, f'{GESTAO}/dashboard?hash={token_projeto(7, "telegram")}&ds=telegram')
        self.assertRegex(url, r'hash=7-[0-9a-f]{32}&ds=telegram$')

    @override_settings(GESTAO_URL=GESTAO + '/', PROJETO_HASH_KEY='chave-a')
    def test_barra_final_do_gestao_url_e_ignorada(self):
        self.assertTrue(self.projeto().url_resultado.startswith(f'{GESTAO}/dashboard?'))

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='chave-a')
    def test_parametros_codificados(self):
        url = self.projeto(prefix='a b&c').url_resultado
        self.assertTrue(url.endswith('&ds=a+b%26c'))
        self.assertEqual(len(re.findall(r'\?hash=', url)), 1)

    @override_settings(GESTAO_URL='', PROJETO_HASH_KEY='chave-a')
    def test_none_sem_gestao_url(self):
        self.assertIsNone(self.projeto().url_resultado)

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='')
    def test_none_sem_chave(self):
        self.assertIsNone(self.projeto().url_resultado)

    @override_settings(GESTAO_URL=GESTAO, PROJETO_HASH_KEY='chave-a')
    def test_none_sem_prefixo(self):
        self.assertIsNone(self.projeto(prefix='').url_resultado)

    def test_none_quando_settings_nao_define_as_chaves(self):
        # o local.py não é versionado e pode não ter GESTAO_URL/PROJETO_HASH_KEY
        with override_settings():
            for nome in ('GESTAO_URL', 'PROJETO_HASH_KEY'):
                if hasattr(settings, nome):
                    delattr(settings, nome)
            self.assertIsNone(self.projeto().url_resultado)
