import csv
import traceback

from io import StringIO

from openpyxl import load_workbook

from datetime import datetime, time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .forms import ImportForm, ImportListaForm, TelegramProjectForm
from .importacao import MAX_LINHAS, importa_lista, le_primeira_coluna
from .models import Canal, Lista, Categoria
from core import log_message
from core.models import Projeto, Termo, TermoStatus, Rede


def import_csv(arquivo) -> list:
    texto = arquivo.read().decode('utf-8')
    csv_reader = csv.DictReader(StringIO(texto))
    lista = []
    for linha in csv_reader:
        username = linha.get('username')
        if username:
            registro = {'username': username,
                        'category': linha.get('category'),
                        'title': linha.get('title'),
                        }
            lista.append(registro)
    return lista


def import_xlsx(arquivo) -> list:

    fieldindex = []
    wb = load_workbook(arquivo)
    ws = wb.active
    for cell in ws[1]:
        fieldindex.append(cell.value)

    lista = []
    for row_list in ws.iter_rows(min_row=2, values_only=True):
        row = {}
        for index, cell in enumerate(row_list):
            row[fieldindex[index]] = cell
        if row.get('username'):
            lista.append({'username': row['username'],
                          'category': row.get('category'),
                          'title': row.get('title'),
                          })

    return lista


@login_required(login_url='/admin/login/')
def telegram_project(request):
    rede = Rede.objects.filter(nome__iexact='Telegram').first()
    if request.method == 'POST':
        form = TelegramProjectForm(request.POST, user=request.user)
        if not rede:
            messages.error(request, 'Rede Telegram não cadastrada. Contate o administrador.')
        elif form.is_valid():
            dados = form.cleaned_data
            tz = timezone.get_current_timezone()
            dtinicio = timezone.make_aware(datetime.combine(dados['dt_inicio'], time.min), tz)
            dtfinal = timezone.make_aware(datetime.combine(dados['dt_final'], time.max.replace(microsecond=0)), tz)
            with transaction.atomic():
                projeto = Projeto.objects.create(nome=dados['nome'], objetivo=dados['objetivo'],
                                                 usuario=request.user, lista_canais=dados['lista'],
                                                 status=Projeto.Status.ATIVO)
                projeto.redes.add(rede)
                for busca in dados['termos']:
                    termo = Termo.objects.create(projeto=projeto, busca=busca, dtinicio=dtinicio, dtfinal=dtfinal)
                    TermoStatus.objects.create(termo=termo, rede=rede)
            messages.success(request, format_html(
                'Para acompanhar o resultado da coleta, clique no link <a href="{0}">{0}</a>',
                projeto.url_resumo))
            return redirect('painel')
    else:
        form = TelegramProjectForm(user=request.user, initial={'lista': request.GET.get('lista')})

    return render(request, 'telegram_project.html', {'form': form})


@login_required(login_url='/admin/login/')
def importar_lista(request):
    if request.method == 'POST':
        form = ImportListaForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                valores = le_primeira_coluna(form.cleaned_data['arquivo'])
                if len(valores) > MAX_LINHAS:
                    raise ValueError(f'O arquivo deve ter no máximo {MAX_LINHAS} linhas.')
                resultado = importa_lista(request.user, form.cleaned_data['nome'],
                                          form.cleaned_data['publica'], valores)
            except ValueError as e:
                form.add_error('arquivo', str(e))
            except Exception:
                print(traceback.format_exc())
                form.add_error('arquivo', 'Não foi possível ler o arquivo. Verifique se é um CSV (UTF-8) ou XLSX válido.')
            else:
                messages.success(request, f'Lista "{resultado["lista"].nome}" criada: '
                                          f'{resultado["lidos"]} linhas lidas, {resultado["novos"]} canais novos, '
                                          f'{resultado["ignorados"]} ignoradas (inválidas).')
                return redirect(f'{reverse("telegram_project")}?lista={resultado["lista"].pk}')
    else:
        form = ImportListaForm(user=request.user)

    return render(request, 'importar_lista.html', {'form': form})


def importacao_canais(request):
    erros = None
    if request.method == 'POST':
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = request.FILES.get('arquivo')
            lista = form.cleaned_data['lista']
            try:
                if arquivo:
                    if arquivo.name.lower().endswith('.csv'):
                        registros = import_csv(arquivo)
                    else:
                        registros = import_xlsx(arquivo)
                    if len(registros) == 0:
                        messages.error(request, 'Nenhum registro foi encontrado')
                    else:
                        tot_registros = 0
                        tot_inclusao = 0
                        for registro in registros:
                            tot_registros += 1
                            username = registro['username']
                            if username.startswith('https://t.me/'):
                                username = username.replace('https://t.me/', '')
                            if username[0] == '@':
                                username = username[1:]
                            username = username.lower().replace('@', '')
                            canal, inclusao = Canal.objects.get_or_create(username=username)
                            if inclusao:
                                tot_inclusao += 1
                                log_message(canal, f'Importado via CSV / {lista.nome}')
                            if registro.get('category'):
                                if request.user.is_superuser:
                                    categoria, inclusao = Categoria.objects.get_or_create(nome=registro['category'])
                                    if inclusao:
                                        log_message(categoria, f'Importado via CSV / {lista.nome}')
                                else:
                                    categoria = Categoria.objects.filter(nome=registro['category']).first()
                                if categoria:
                                    canal.categorias.add(categoria)
                            lista.canais.add(canal)

                        messages.info(request, f'Total de registros lidos: {tot_registros}')
                        messages.info(request, f'Total de registros incluídos: {tot_inclusao}')
                        return redirect(reverse('admin:index'))
                else:
                    messages.error(request, 'Nenhum arquivo enviado. Tente utilizar outro navegador.')

            except Exception as e:
                message = ''.join(traceback.TracebackException.from_exception(e).format())
                print(message)
                # sendmail('Erro Importação Lattes', [settings.REPLY_TO_EMAIL], message=message)
                messages.error(request, 'Houve um erro durante a importação. Já estamos averiguando o problema')

            return redirect('importacao_canais')
    else:
        form = ImportForm()

    return render(request, 'importacao.html', {'form': form, 'erros': erros})

