from unittest import mock

from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Projeto, Rede, Termo, TermoStatus
from telegram.models import Lista


class TelegramProjectTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.rede = Rede.objects.create(nome='Telegram')
        cls.user = User.objects.create_user('ana', password='x')
        cls.outro = User.objects.create_user('bia', password='x')
        cls.publica = Lista.objects.create(nome='Publica', dono=cls.outro, publica=True)
        cls.propria = Lista.objects.create(nome='Propria', dono=cls.user)
        cls.alheia = Lista.objects.create(nome='Alheia', dono=cls.outro)

    def setUp(self):
        self.client.force_login(self.user)

    def dados(self, **extra):
        dados = {'nome': 'Proj', 'objetivo': 'Estudo', 'lista': self.publica.pk,
                 'dt_inicio': '2025-01-01', 'dt_final': '2025-02-01',
                 'termos': 'ecologia OR ecológico\n\n  ecologia AND ecológico  '}
        dados.update(extra)
        return dados

    def test_anonimo_redireciona_para_login(self):
        self.client.logout()
        for resposta in (self.client.get('/telegram_project/'), self.client.post('/telegram_project/', self.dados())):
            self.assertEqual(resposta.status_code, 302)
            self.assertTrue(resposta.url.startswith('/admin/login/'))
        self.assertEqual(Projeto.objects.count(), 0)

    def test_get_lista_publicas_e_proprias(self):
        resposta = self.client.get('/telegram_project/')
        self.assertEqual(resposta.status_code, 200)
        listas = set(resposta.context['form'].fields['lista'].queryset)
        self.assertEqual(listas, {self.publica, self.propria})

    def test_post_valido_cria_projeto_termos_e_redireciona(self):
        resposta = self.client.post('/telegram_project/', self.dados())
        self.assertRedirects(resposta, '/painel/', fetch_redirect_response=False)
        projeto = Projeto.objects.get()
        self.assertEqual(projeto.usuario, self.user)
        self.assertEqual(projeto.lista_canais, self.publica)
        self.assertEqual(list(projeto.redes.all()), [self.rede])
        self.assertEqual(sorted(t.busca for t in projeto.termo_set.all()),
                         ['ecologia AND ecológico', 'ecologia OR ecológico'])
        self.assertEqual(TermoStatus.objects.filter(rede=self.rede).count(), 2)
        mensagens = [str(m) for m in self.client.get('/painel/').context['messages']]
        self.assertIn(projeto.url_resumo, mensagens[0])

    def test_data_final_anterior_rejeitada(self):
        resposta = self.client.post('/telegram_project/', self.dados(dt_final='2024-12-31'))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('dt_final', resposta.context['form'].errors)
        self.assertEqual(Projeto.objects.count(), 0)

    def test_termos_invalidos(self):
        for termo in ('ecologia AND', 'OR x', 'a AND OR b', '\n  \n'):
            resposta = self.client.post('/telegram_project/', self.dados(termos=termo))
            self.assertEqual(resposta.status_code, 200, termo)
            self.assertIn('termos', resposta.context['form'].errors, termo)
        self.assertEqual(Projeto.objects.count(), 0)

    def test_conectivo_minusculo_aceito(self):
        resposta = self.client.post('/telegram_project/', self.dados(termos='ecologia and x'))
        self.assertEqual(resposta.status_code, 302)

    def test_nome_longo_rejeitado(self):
        resposta = self.client.post('/telegram_project/', self.dados(nome='x' * 41))
        self.assertIn('nome', resposta.context['form'].errors)

    def test_lista_privada_de_outro_rejeitada(self):
        resposta = self.client.post('/telegram_project/', self.dados(lista=self.alheia.pk))
        self.assertIn('lista', resposta.context['form'].errors)
        self.assertEqual(Projeto.objects.count(), 0)

    def test_falha_em_termo_desfaz_projeto(self):
        with mock.patch('telegram.views.Termo.objects.create', side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                self.client.post('/telegram_project/', self.dados())
        self.assertEqual(Projeto.objects.count(), 0)
        self.assertEqual(Termo.objects.count(), 0)

    def test_sem_rede_telegram_nao_grava(self):
        Rede.objects.all().delete()
        resposta = self.client.post('/telegram_project/', self.dados())
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Projeto.objects.count(), 0)

    def test_painel_aponta_para_a_view(self):
        self.assertContains(self.client.get('/painel/'), 'href="/telegram_project/"')
