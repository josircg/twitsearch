from io import BytesIO
from unittest import mock

from openpyxl import Workbook

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from core.models import Projeto, Rede, Termo, TermoStatus
from telegram.models import Canal, Lista


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


class ImportarListaTests(TestCase):

    URL = '/telegram_project/importar_lista/'

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('ana', password='x')

    def setUp(self):
        self.client.force_login(self.user)

    def csv(self, conteudo, nome='canais.csv'):
        return SimpleUploadedFile(nome, conteudo.encode('utf-8'), content_type='text/csv')

    def xlsx(self, linhas, nome='canais.xlsx'):
        wb = Workbook()
        for linha in linhas:
            wb.active.append(linha)
        buffer = BytesIO()
        wb.save(buffer)
        return SimpleUploadedFile(nome, buffer.getvalue())

    def envia(self, arquivo, nome='Minha lista', publica='False', **extra):
        return self.client.post(self.URL, {'nome': nome, 'publica': publica, 'arquivo': arquivo, **extra})

    def test_anonimo_redireciona_para_login(self):
        self.client.logout()
        for resposta in (self.client.get(self.URL), self.envia(self.csv('@canal_um'))):
            self.assertEqual(resposta.status_code, 302)
            self.assertTrue(resposta.url.startswith('/admin/login/'))
        self.assertEqual(Lista.objects.count(), 0)

    def test_get_exibe_hint(self):
        resposta = self.client.get(self.URL)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'apenas uma coluna')

    def test_csv_cria_lista_canais_e_redireciona(self):
        conteudo = 'username\nhttps://t.me/Canal_Um\n@canal_dois\ncanal_tres\n\nt.me/canal_um/123\n'
        resposta = self.envia(self.csv(conteudo))
        lista = Lista.objects.get()
        self.assertRedirects(resposta, f'/telegram_project/?lista={lista.pk}', fetch_redirect_response=False)
        self.assertEqual(lista.dono, self.user)
        self.assertFalse(lista.publica)
        self.assertEqual(sorted(c.username for c in lista.canais.all()), ['canal_dois', 'canal_tres', 'canal_um'])

    def test_csv_com_bom_e_sem_cabecalho(self):
        arquivo = SimpleUploadedFile('c.csv', '﻿@canal_um\n@canal_dois\n'.encode('utf-8'))
        self.envia(arquivo, publica='True')
        lista = Lista.objects.get()
        self.assertTrue(lista.publica)
        self.assertEqual(lista.canais.count(), 2)

    def test_xlsx(self):
        self.envia(self.xlsx([['url'], ['https://t.me/canal_um'], ['@canal_dois']]))
        self.assertEqual(Lista.objects.get().canais.count(), 2)

    def test_invalidos_ignorados_e_duplicados_reaproveitados(self):
        Canal.objects.create(username='canal_um')
        resposta = self.envia(self.csv('canal_um\nCANAL_UM\n12345678\nt.me/+abcdef\nab\ncanal_dois\n'), follow=True)
        lista = Lista.objects.get()
        self.assertEqual(Canal.objects.count(), 2)
        self.assertEqual(sorted(c.username for c in lista.canais.all()), ['canal_dois', 'canal_um'])
        mensagem = str(list(get_messages(resposta.wsgi_request))[0])
        self.assertIn('1 canais novos', mensagem)
        self.assertIn('3 ignoradas', mensagem)

    def test_sem_canal_valido_nao_cria_lista(self):
        resposta = self.envia(self.csv('12345\n+abc\n'))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('arquivo', resposta.context['form'].errors)
        self.assertEqual(Lista.objects.count(), 0)

    def test_extensao_invalida(self):
        resposta = self.envia(SimpleUploadedFile('c.txt', b'@canal_um'))
        self.assertIn('arquivo', resposta.context['form'].errors)
        self.assertEqual(Lista.objects.count(), 0)

    def test_limite_de_linhas(self):
        linhas = '\n'.join(f'canal_{i:05d}' for i in range(5001))
        resposta = self.envia(self.csv(linhas))
        self.assertIn('arquivo', resposta.context['form'].errors)
        self.assertEqual(Lista.objects.count(), 0)

    def test_nome_duplicado_do_mesmo_dono_rejeitado(self):
        Lista.objects.create(nome='Minha lista', dono=self.user)
        resposta = self.envia(self.csv('@canal_um'))
        self.assertIn('nome', resposta.context['form'].errors)
        self.assertEqual(Lista.objects.count(), 1)

    def test_nome_igual_de_outro_dono_aceito(self):
        outro = User.objects.create_user('bia', password='x')
        Lista.objects.create(nome='Minha lista', dono=outro)
        self.envia(self.csv('@canal_um'))
        self.assertEqual(Lista.objects.filter(dono=self.user).count(), 1)

    def test_arquivo_corrompido(self):
        resposta = self.envia(SimpleUploadedFile('c.xlsx', b'nao e um xlsx'))
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('arquivo', resposta.context['form'].errors)
        self.assertEqual(Lista.objects.count(), 0)

    def test_falha_ao_criar_canal_desfaz_lista(self):
        with mock.patch('telegram.importacao.Canal.objects.get_or_create', side_effect=RuntimeError):
            resposta = self.envia(self.csv('@canal_um'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Lista.objects.count(), 0)

    def test_projeto_preseleciona_lista_importada(self):
        lista = Lista.objects.create(nome='Nova', dono=self.user)
        resposta = self.client.get(f'/telegram_project/?lista={lista.pk}')
        self.assertEqual(resposta.context['form']['lista'].value(), str(lista.pk))

    def test_botao_do_projeto_aponta_para_importar_lista(self):
        self.assertContains(self.client.get('/telegram_project/'), f'href="{self.URL}"')
