import zoneinfo

from datetime import datetime, timezone
from io import BytesIO
from unittest import mock
from urllib.parse import parse_qs, urlencode

from openpyxl import Workbook

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import Context, Template
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone as dj_timezone

from core.models import Projeto, Rede, Termo, TermoStatus
from telegram.datalake import PaginaMensagens, busca_mensagens, formata_mensagem, paginas_visiveis, periodo_canal
from telegram.forms import FiltroMensagensForm, listas_visiveis
from telegram.models import Canal, Lista
from telegram.templatetags.telegram_tags import destaca, milhar


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



def mensagem_pg(message_id=1, texto='olá', **extra):
    # documento como gravado por serializa_mensagem
    doc = {'id': f'1_{message_id}', 'message_id': message_id, 'channel_id': 1001, 'username': 'canal',
           'message': texto, 'timestamp': '2025-03-10T15:30:00+00:00', 'views': 10, 'forwards': 2,
           'media_type': None}
    doc.update(extra)
    return (doc,)


def conexao_falsa(total=0, linhas=()):
    conn = mock.MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.return_value = (total,)
    cur.fetchall.return_value = list(linhas)
    return conn, cur


class ListasVisiveisTests(TestCase):

    def test_publicas_e_proprias_ordenadas_por_nome(self):
        ana, bia = User.objects.create_user('ana'), User.objects.create_user('bia')
        Lista.objects.create(nome='B publica', dono=bia, publica=True)
        Lista.objects.create(nome='A propria', dono=ana)
        Lista.objects.create(nome='C alheia', dono=bia)
        self.assertEqual([lista.nome for lista in listas_visiveis(ana)], ['A propria', 'B publica'])


class ListaCanaisViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('ana', password='x')
        cls.outro = User.objects.create_user('bia', password='x')
        cls.publica = Lista.objects.create(nome='Publica', dono=cls.outro, publica=True)
        cls.propria = Lista.objects.create(nome='Propria', dono=cls.user)
        cls.alheia = Lista.objects.create(nome='Alheia', dono=cls.outro)
        cls.c1 = Canal.objects.create(username='c1', num_participantes=10)
        cls.c2 = Canal.objects.create(username='c2', num_participantes=30)
        cls.c3 = Canal.objects.create(username='c3', num_participantes=30)
        cls.secreto = Canal.objects.create(username='secreto', num_participantes=99)
        cls.publica.canais.add(cls.c1, cls.c2)
        cls.propria.canais.add(cls.c2, cls.c3)
        cls.alheia.canais.add(cls.secreto)

    def setUp(self):
        self.client.force_login(self.user)

    def test_anonimo_redireciona_para_login(self):
        self.client.logout()
        for url in ('/telegram/lista_canais/', '/telegram/canal/1/'):
            resposta = self.client.get(url)
            self.assertEqual(resposta.status_code, 302)
            self.assertTrue(resposta.url.startswith('/admin/login/'))

    def test_rotas(self):
        self.assertEqual(reverse('lista_canais'), '/telegram/lista_canais/')
        self.assertEqual(reverse('canal_mensagens', args=[7]), '/telegram/canal/7/')

    def test_tags_publicas_e_proprias_com_total(self):
        resposta = self.client.get('/telegram/lista_canais/')
        self.assertEqual(resposta.status_code, 200)
        listas = {item['nome']: item for item in resposta.context['listas']}
        self.assertEqual(set(listas), {'Publica', 'Propria'})
        self.assertEqual(listas['Publica']['total'], 2)
        self.assertTrue(listas['Publica']['publica'])
        self.assertTrue(resposta.context['tem_listas'])
        self.assertEqual(resposta.context['importar_url'], '/telegram_project/importar_lista/')
        self.assertEqual(resposta.context['limpar_url'], '/telegram/lista_canais/')

    def test_sem_selecao_nao_ha_grid(self):
        resposta = self.client.get('/telegram/lista_canais/')
        self.assertIsNone(resposta.context['page_obj'])
        self.assertEqual(resposta.context['total_canais'], 0)
        self.assertEqual(resposta.context['paginas'], [])
        self.assertEqual(resposta.context['voltar_qs'], '')
        self.assertEqual(resposta.context['selecionadas'], [])

    def test_sem_listas_visiveis(self):
        self.client.force_login(User.objects.create_user('nova', password='x'))
        Lista.objects.filter(publica=True).update(publica=False)
        resposta = self.client.get('/telegram/lista_canais/')
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(resposta.context['tem_listas'])

    def test_lista_privada_alheia_e_ignorada(self):
        resposta = self.client.get(f'/telegram/lista_canais/?lista={self.alheia.pk}&lista=abc&lista=99999')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['selecionadas'], [])
        self.assertIsNone(resposta.context['page_obj'])
        self.assertEqual(resposta.context['total_canais'], 0)

    def test_canal_em_duas_listas_aparece_uma_vez(self):
        resposta = self.client.get(f'/telegram/lista_canais/?lista={self.publica.pk}&lista={self.propria.pk}')
        usernames = [c.username for c in resposta.context['page_obj']]
        self.assertEqual(usernames, ['c2', 'c3', 'c1'])  # participantes desc, depois username
        self.assertEqual(resposta.context['total_canais'], 3)
        self.assertEqual(len(resposta.context['selecionadas']), 2)

    def test_toggle_urls(self):
        resposta = self.client.get(f'/telegram/lista_canais/?lista={self.publica.pk}')
        itens = {i['id']: i for i in resposta.context['listas']}
        self.assertTrue(itens[self.publica.pk]['selecionada'])
        self.assertFalse(itens[self.propria.pk]['selecionada'])
        self.assertEqual(itens[self.publica.pk]['url'], '/telegram/lista_canais/')
        self.assertEqual(itens[self.propria.pk]['url'],
                         f'/telegram/lista_canais/?lista={self.publica.pk}&lista={self.propria.pk}')

    def test_voltar_qs(self):
        resposta = self.client.get(f'/telegram/lista_canais/?lista={self.publica.pk}&lista={self.propria.pk}')
        voltar = parse_qs(resposta.context['voltar_qs'])['voltar'][0]
        self.assertEqual(voltar, f'lista={self.publica.pk}&lista={self.propria.pk}')

    def test_paginacao_de_50_preserva_selecao(self):
        Canal.objects.bulk_create([Canal(username=f'x{i:03d}') for i in range(60)])
        self.publica.canais.add(*Canal.objects.filter(username__startswith='x'))
        base = f'/telegram/lista_canais/?lista={self.publica.pk}'
        resposta = self.client.get(base + '&page=2')
        self.assertEqual(resposta.context['total_canais'], 62)
        self.assertEqual(resposta.context['page_obj'].number, 2)
        self.assertEqual(len(resposta.context['page_obj']), 12)
        self.assertEqual(resposta.context['query_sem_page'], f'lista={self.publica.pk}')
        self.assertEqual(resposta.context['paginas'], [1, 2])
        # página inválida cai na primeira/última sem erro
        self.assertEqual(self.client.get(base + '&page=abc').context['page_obj'].number, 1)
        self.assertEqual(self.client.get(base + '&page=99').context['page_obj'].number, 2)
        # o rodapé usa paginator.num_pages da Page do Django (regressão: não era renderizado)
        self.assertContains(resposta, 'Mostrando <strong>51–62</strong> de 62', html=False)
        self.assertContains(resposta, f'href="?lista={self.publica.pk}&amp;page=1"')
        self.assertContains(resposta, 'Ir para a página')

    def test_pagina_unica_mostra_rodape_sem_ir_para(self):
        resposta = self.client.get(f'/telegram/lista_canais/?lista={self.publica.pk}')
        self.assertContains(resposta, 'Mostrando <strong>1–2</strong> de 2', html=False)
        self.assertNotContains(resposta, 'Ir para a página')


@mock.patch('telegram.views.busca_mensagens')
class CanalMensagensViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('ana', password='x')
        cls.outro = User.objects.create_user('bia', password='x')
        cls.publica = Lista.objects.create(nome='Publica', dono=cls.outro, publica=True)
        cls.alheia = Lista.objects.create(nome='Alheia', dono=cls.outro)
        cls.canal = Canal.objects.create(username='canal', id_numerico=1001)
        cls.sem_id = Canal.objects.create(username='novo')
        cls.privado = Canal.objects.create(username='privado', id_numerico=2002)
        cls.orfao = Canal.objects.create(username='orfao', id_numerico=3003)
        cls.publica.canais.add(cls.canal, cls.sem_id)
        cls.alheia.canais.add(cls.privado)

    def setUp(self):
        self.client.force_login(self.user)
        self.periodo = mock.patch('telegram.views.periodo_canal', return_value=()).start()
        self.addCleanup(mock.patch.stopall)

    def url(self, pk=None, **params):
        base = reverse('canal_mensagens', args=[pk or self.canal.pk])
        return f'{base}?{urlencode(params)}' if params else base

    def amostra(self):
        return [{'message_id': 1, 'texto': 'olá', 'data': None, 'views': 1, 'forwards': 0, 'midia': None,
                 'url': 'https://t.me/canal/1'}]

    def test_paginacao_renderizada(self, busca):
        busca.return_value = (60, self.amostra())
        resposta = self.client.get(self.url(termo='olá', page=2))
        self.assertContains(resposta, 'Mostrando <strong>26–50</strong> de 60', html=False)
        self.assertContains(resposta, 'Página <strong>2</strong> de 3', html=False)
        self.assertContains(resposta, 'page=3"')
        self.assertContains(resposta, 'Ir para a página')
        # página única: só a contagem, sem navegação compacta nem "Ir para"
        busca.return_value = (1, self.amostra())
        resposta = self.client.get(self.url())
        self.assertContains(resposta, 'Mostrando <strong>1–1</strong> de 1', html=False)
        self.assertNotContains(resposta, 'Ir para a página')
        self.assertNotContains(resposta, 'class="tc-mini"')

    def test_filtro_de_data_vazio_mostra_periodo_coletado(self, busca):
        busca.return_value = (0, [])
        tz = dj_timezone.get_current_timezone()
        self.periodo.return_value = (datetime(2025, 1, 1, 9, 0, tzinfo=tz), datetime(2025, 2, 20, 15, 5, tzinfo=tz))
        resposta = self.client.get(self.url(dt_inicio='2025-03-20', dt_final='2025-03-21'))
        self.periodo.assert_called_once_with(1001)
        self.assertContains(resposta, 'vão de <strong>01/01/2025</strong> a <strong>20/02/2025</strong>', html=False)
        # canal sem nenhuma mensagem coletada
        self.periodo.return_value = ()
        resposta = self.client.get(self.url(dt_inicio='2025-03-20'))
        self.assertContains(resposta, 'Ainda não há mensagens coletadas deste canal.')

    def test_periodo_so_e_consultado_com_filtro_de_data_sem_resultado(self, busca):
        busca.return_value = (0, [])
        self.client.get(self.url(termo='nada'))
        busca.return_value = (5, self.amostra())
        self.client.get(self.url(dt_inicio='2025-01-01'))
        self.periodo.assert_not_called()

    def test_canal_fora_das_listas_visiveis_da_404(self, busca):
        for canal in (self.privado, self.orfao):
            self.assertEqual(self.client.get(self.url(canal.pk)).status_code, 404)
        self.assertEqual(self.client.get(self.url(99999)).status_code, 404)
        busca.assert_not_called()

    def test_canal_sem_id_numerico_nao_consulta_datalake(self, busca):
        resposta = self.client.get(self.url(self.sem_id.pk))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['estado'], 'nao_sincronizado')
        busca.assert_not_called()

    def test_data_final_anterior_a_inicial_nao_consulta_datalake(self, busca):
        resposta = self.client.get(self.url(dt_inicio='2025-02-01', dt_final='2025-01-01'))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['estado'], 'form_invalido')
        self.assertEqual(resposta.context['form'].errors['dt_final'],
                         ['A data final deve ser igual ou posterior à data inicial.'])
        busca.assert_not_called()

    def test_data_invalida_nao_consulta_datalake(self, busca):
        resposta = self.client.get(self.url(dt_inicio='01/02/2025'))
        self.assertEqual(resposta.context['estado'], 'form_invalido')
        busca.assert_not_called()

    def test_sem_filtros_usa_padroes(self, busca):
        busca.return_value = (1, self.amostra())
        resposta = self.client.get(self.url())
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['estado'], 'ok')
        busca.assert_called_once_with(1001, dt_inicio=None, dt_final=None, termo=None, limit=25, offset=0)
        self.assertEqual(resposta.context['mensagens'], self.amostra())
        self.assertEqual(resposta.context['pagina'].count, 1)
        self.assertEqual(resposta.context['termo'], '')
        self.assertEqual(resposta.context['voltar_url'], '/telegram/lista_canais/')

    def test_filtros_repassados_no_fuso_local(self, busca):
        busca.return_value = (0, [])
        resposta = self.client.get(self.url(dt_inicio='2025-03-01', dt_final='2025-03-31', termo='  100%_x  '))
        tz = zoneinfo.ZoneInfo('America/Sao_Paulo')
        kwargs = busca.call_args.kwargs
        self.assertEqual(busca.call_args.args, (1001,))
        self.assertEqual(kwargs['dt_inicio'], datetime(2025, 3, 1, 0, 0, tzinfo=tz))
        self.assertEqual(kwargs['dt_final'], datetime(2025, 3, 31, 23, 59, 59, 999999, tzinfo=tz))
        self.assertEqual(kwargs['termo'], '100%_x')
        self.assertEqual(resposta.context['termo'], '100%_x')
        self.assertEqual(resposta.context['pagina'].count, 0)

    def test_paginacao_repassa_limit_e_offset(self, busca):
        busca.return_value = (120, self.amostra())
        resposta = self.client.get(self.url(page=3, por_pagina=25, termo='a'))
        self.assertEqual(busca.call_args.kwargs['limit'], 25)
        self.assertEqual(busca.call_args.kwargs['offset'], 50)
        self.assertEqual(resposta.context['pagina'].number, 3)
        self.assertEqual(resposta.context['pagina'].num_pages, 5)
        self.assertEqual(resposta.context['paginas'], [1, 2, 3, 4, 5])
        self.assertEqual(resposta.context['query_sem_page'], 'por_pagina=25&termo=a')

    def test_por_pagina_invalido_cai_para_25(self, busca):
        busca.return_value = (10, self.amostra())
        for valor in ('500', 'abc', '0', '-5', ''):
            resposta = self.client.get(self.url(por_pagina=valor))
            self.assertEqual(resposta.context['estado'], 'ok', valor)
            self.assertEqual(busca.call_args.kwargs['limit'], 25, valor)
        busca.return_value = (500, self.amostra())
        self.client.get(self.url(por_pagina=100, page=2))
        self.assertEqual((busca.call_args.kwargs['limit'], busca.call_args.kwargs['offset']), (100, 100))

    def test_page_invalida_vira_primeira(self, busca):
        busca.return_value = (100, self.amostra())
        for valor in ('abc', '0', '-3', ''):
            resposta = self.client.get(self.url(page=valor))
            self.assertEqual(resposta.context['pagina'].number, 1, valor)
            self.assertEqual(busca.call_args.kwargs['offset'], 0, valor)

    def test_page_acima_da_ultima_refaz_busca_na_ultima(self, busca):
        busca.side_effect = [(60, []), (60, self.amostra())]
        resposta = self.client.get(self.url(page=99))
        self.assertEqual(busca.call_count, 2)
        self.assertEqual(busca.call_args.kwargs['offset'], 50)
        self.assertEqual(resposta.context['pagina'].number, 3)
        self.assertEqual(resposta.context['mensagens'], self.amostra())

    def test_erro_no_datalake_mostra_estado_amigavel(self, busca):
        busca.side_effect = RuntimeError('conexão recusada')
        with self.assertLogs('telegram.views', level='ERROR'):
            resposta = self.client.get(self.url())
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['estado'], 'erro_datalake')
        self.assertEqual(resposta.context['mensagens'], [])
        self.assertIsNone(resposta.context['pagina'])

    def test_voltar_so_aceita_lista(self, busca):
        busca.return_value = (0, [])
        resposta = self.client.get(self.url(voltar='lista=1&lista=3'))
        self.assertEqual(resposta.context['voltar_url'], '/telegram/lista_canais/?lista=1&lista=3')
        self.assertEqual(resposta.context['voltar'], 'lista=1&lista=3')
        resposta = self.client.get(self.url(voltar='https://evil.example/'))
        self.assertEqual(resposta.context['voltar_url'], '/telegram/lista_canais/')
        self.assertEqual(resposta.context['voltar'], '')

    def test_mensagem_sem_texto_chega_ao_contexto(self, busca):
        busca.return_value = (1, [dict(self.amostra()[0], texto=None, midia='Foto')])
        resposta = self.client.get(self.url())
        self.assertIsNone(resposta.context['mensagens'][0]['texto'])


class FiltroMensagensFormTests(SimpleTestCase):

    def test_vazio_e_valido_com_padrao(self):
        form = FiltroMensagensForm({})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['por_pagina'], 25)
        self.assertIsNone(form.cleaned_data['dt_inicio'])
        self.assertEqual(form.cleaned_data['termo'], '')

    def test_por_pagina(self):
        for bruto, esperado in (('25', 25), ('50', 50), ('100', 100), ('500', 25), ('x', 25), ('', 25)):
            form = FiltroMensagensForm({'por_pagina': bruto})
            self.assertTrue(form.is_valid(), bruto)
            self.assertEqual(form.cleaned_data['por_pagina'], esperado, bruto)

    def test_termo_strip_e_limite(self):
        form = FiltroMensagensForm({'termo': '  vacina '})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['termo'], 'vacina')
        self.assertFalse(FiltroMensagensForm({'termo': 'a' * 201}).is_valid())

    def test_datas(self):
        self.assertTrue(FiltroMensagensForm({'dt_inicio': '2025-01-01', 'dt_final': '2025-01-01'}).is_valid())
        form = FiltroMensagensForm({'dt_inicio': '2025-01-02', 'dt_final': '2025-01-01'})
        self.assertFalse(form.is_valid())
        self.assertIn('dt_final', form.errors)
        self.assertFalse(FiltroMensagensForm({'dt_inicio': '02/01/2025'}).is_valid())

    def test_widgets(self):
        form = FiltroMensagensForm()
        self.assertEqual(form.fields['dt_inicio'].widget.input_type, 'date')
        self.assertEqual(form.fields['termo'].widget.input_type, 'search')
        self.assertEqual(form.fields['por_pagina'].widget.attrs['class'], 'form-select')
        self.assertEqual(form.fields['termo'].widget.attrs['class'], 'form-control')


class PaginacaoTests(SimpleTestCase):

    def test_paginas_visiveis(self):
        self.assertEqual(paginas_visiveis(50, 195), [1, None, 49, 50, 51, None, 195])
        self.assertEqual(paginas_visiveis(1, 195), [1, 2, 3, 4, 5, None, 195])
        self.assertEqual(paginas_visiveis(4, 195), [1, 2, 3, 4, 5, None, 195])
        self.assertEqual(paginas_visiveis(195, 195), [1, None, 191, 192, 193, 194, 195])
        self.assertEqual(paginas_visiveis(192, 195), [1, None, 191, 192, 193, 194, 195])
        self.assertEqual(paginas_visiveis(1, 1), [1])
        self.assertEqual(paginas_visiveis(2, 3), [1, 2, 3])
        self.assertEqual(paginas_visiveis(3, 7), [1, 2, 3, 4, 5, None, 7])

    def test_pagina_mensagens(self):
        pagina = PaginaMensagens(3, 25, 120)
        self.assertEqual((pagina.number, pagina.per_page, pagina.count, pagina.num_pages), (3, 25, 120, 5))
        self.assertTrue(pagina.has_previous() and pagina.has_next())
        self.assertEqual((pagina.previous_page_number(), pagina.next_page_number()), (2, 4))
        self.assertEqual((pagina.start_index(), pagina.end_index()), (51, 75))
        self.assertEqual(pagina.paginas_visiveis, [1, 2, 3, 4, 5])

    def test_ultima_pagina_e_limites(self):
        pagina = PaginaMensagens(5, 25, 120)
        self.assertFalse(pagina.has_next())
        self.assertEqual((pagina.start_index(), pagina.end_index()), (101, 120))
        self.assertFalse(PaginaMensagens(1, 25, 120).has_previous())

    def test_normaliza_pagina(self):
        self.assertEqual(PaginaMensagens('abc', 25, 100).number, 1)
        self.assertEqual(PaginaMensagens(None, 25, 100).number, 1)
        self.assertEqual(PaginaMensagens(0, 25, 100).number, 1)
        self.assertEqual(PaginaMensagens(-2, 25, 100).number, 1)
        self.assertEqual(PaginaMensagens(99, 25, 100).number, 4)
        self.assertEqual(PaginaMensagens('2', 25, 100).number, 2)

    def test_sem_mensagens(self):
        pagina = PaginaMensagens(1, 25, 0)
        self.assertEqual(pagina.num_pages, 1)
        self.assertEqual((pagina.start_index(), pagina.end_index()), (0, 0))
        self.assertFalse(pagina.has_next() or pagina.has_previous())


class BuscaMensagensTests(SimpleTestCase):

    def test_sql_parametrizado_e_conexao_fechada(self):
        conn, cur = conexao_falsa(total=2, linhas=[mensagem_pg(2, 'dois'), mensagem_pg(1, None, media_type='photo')])
        ini = datetime(2025, 3, 1, tzinfo=timezone.utc)
        perigoso = "50%_off\\' OR 1=1 --"
        with mock.patch('telegram.datalake.connect_postgresql', return_value=conn) as conecta:
            total, mensagens = busca_mensagens(1001, ini, None, perigoso, limit=50, offset=100)
        conecta.assert_called_once_with('pg_baoba')
        conn.close.assert_called_once()
        self.assertEqual(total, 2)
        self.assertEqual(cur.execute.call_count, 2)
        (sql_total, p_total), (sql_pagina, p_pagina) = [c.args for c in cur.execute.call_args_list]
        self.assertIn('count(*)', sql_total)
        self.assertIn('LIMIT %(limit)s OFFSET %(offset)s', sql_pagina)
        self.assertIn("ORDER BY telegram_ts(source->>'timestamp') DESC", sql_pagina)
        for sql in (sql_total, sql_pagina):
            self.assertIn("telegram_ts(source->>'timestamp') >= %(ini)s", sql)
            self.assertIn("ILIKE %(termo)s ESCAPE '\\'", sql)
            self.assertNotIn('1001', sql)
            self.assertNotIn('OR 1=1', sql)
            self.assertNotIn('50%', sql)
        self.assertEqual(p_total, {'canal': 1001, 'ini': ini, 'fim': None,
                                   'termo': "%50\\%\\_off\\\\' OR 1=1 --%"})
        self.assertEqual(p_pagina, {**p_total, 'limit': 50, 'offset': 100})
        self.assertEqual([m['message_id'] for m in mensagens], [2, 1])
        self.assertEqual(mensagens[1]['midia'], 'Foto')
        self.assertIsNone(mensagens[1]['texto'])

    def test_sem_termo_envia_none(self):
        conn, cur = conexao_falsa()
        with mock.patch('telegram.datalake.connect_postgresql', return_value=conn):
            self.assertEqual(busca_mensagens(1), (0, []))
        self.assertIsNone(cur.execute.call_args_list[0].args[1]['termo'])
        self.assertEqual(cur.execute.call_args_list[1].args[1]['limit'], 25)

    def test_conexao_fechada_mesmo_com_erro(self):
        conn, cur = conexao_falsa()
        cur.execute.side_effect = RuntimeError('falhou')
        with mock.patch('telegram.datalake.connect_postgresql', return_value=conn):
            with self.assertRaises(RuntimeError):
                busca_mensagens(1)
        conn.close.assert_called_once()

    def test_erro_de_conexao_propaga(self):
        with mock.patch('telegram.datalake.connect_postgresql', side_effect=RuntimeError('sem rede')):
            with self.assertRaises(RuntimeError):
                busca_mensagens(1)

    def test_periodo_canal(self):
        conn, cur = conexao_falsa(total=0, linhas=[])
        cur.fetchone.return_value = (datetime(2025, 1, 1, 3, 0, tzinfo=timezone.utc),
                                     datetime(2025, 2, 20, 18, 5, tzinfo=timezone.utc))
        with mock.patch('telegram.datalake.connect_postgresql', return_value=conn):
            inicio, fim = periodo_canal(1001)
        self.assertEqual((inicio.day, inicio.hour, fim.day, fim.hour), (1, 0, 20, 15))
        self.assertEqual(cur.execute.call_args[0][1], {'canal': 1001})
        conn.close.assert_called_once()
        cur.fetchone.return_value = (None, None)
        with mock.patch('telegram.datalake.connect_postgresql', return_value=conn):
            self.assertEqual(periodo_canal(1001), ())

    def test_formata_mensagem(self):
        doc = mensagem_pg(7, 'texto', username='meucanal', views=None, forwards='3',
                          timestamp='2025-03-10T23:30:00+00:00')[0]
        msg = formata_mensagem(doc)
        self.assertEqual(msg['url'], 'https://t.me/meucanal/7')
        self.assertEqual((msg['views'], msg['forwards']), (0, 3))
        self.assertTrue(dj_timezone.is_aware(msg['data']))
        self.assertEqual(msg['data'].isoformat(), '2025-03-10T20:30:00-03:00')  # America/Sao_Paulo

    def test_midia(self):
        for bruto, rotulo in (('photo', 'Foto'), ('document', 'Documento'), ('MessageMediaWebPage', 'Link'),
                              ('MessageMediaPoll', 'Mídia'), (None, None), ('', None)):
            self.assertEqual(formata_mensagem(mensagem_pg(media_type=bruto)[0])['midia'], rotulo, bruto)
        self.assertIsNone(formata_mensagem(mensagem_pg(texto='')[0])['texto'])


class TemplateTagsTests(SimpleTestCase):

    def test_milhar(self):
        self.assertEqual(milhar(4870), '4.870')
        self.assertEqual(milhar(1234567), '1.234.567')
        self.assertEqual(milhar(999), '999')
        self.assertEqual(milhar(0), '0')
        self.assertEqual(milhar(None), '0')

    def test_destaca(self):
        self.assertEqual(destaca('A vacina chegou. VACINA!', 'vacina'),
                         'A <mark>vacina</mark> chegou. <mark>VACINA</mark>!')
        self.assertEqual(destaca('texto', ''), 'texto')
        self.assertEqual(destaca('texto', None), 'texto')

    def test_destaca_nao_permite_injecao(self):
        resultado = destaca('<script>alert(1)</script> ok', 'ok')
        self.assertEqual(resultado, '&lt;script&gt;alert(1)&lt;/script&gt; <mark>ok</mark>')
        self.assertEqual(destaca('texto', '<b>'), 'texto')
        self.assertEqual(destaca('a <b> c', '<b>'), 'a <mark>&lt;b&gt;</mark> c')
        self.assertEqual(destaca('a & b', 'amp'), 'a &amp; b')
        self.assertEqual(destaca('a.b', '.'), 'a<mark>.</mark>b')

    def test_destaca_em_template(self):
        saida = Template('{% load telegram_tags %}{{ t|destaca:q }}|{{ n|milhar }}').render(
            Context({'t': '<i>x</i> vacina', 'q': 'vacina', 'n': 12345}))
        self.assertEqual(saida, '&lt;i&gt;x&lt;/i&gt; <mark>vacina</mark>|12.345')
