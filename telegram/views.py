import csv
import logging
import traceback

from io import StringIO

from openpyxl import load_workbook

from datetime import datetime, time
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .datalake import PaginaMensagens, busca_mensagens, paginas_visiveis, periodo_canal
from .forms import FiltroMensagensForm, ImportForm, ImportListaForm, TelegramProjectForm, listas_visiveis
from .importacao import MAX_LINHAS, importa_lista, le_primeira_coluna
from .models import Canal, Lista, Categoria
from core import log_message
from core.models import Projeto, Termo, TermoStatus, Rede

logger = logging.getLogger(__name__)


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


def periodo_coleta(dt_inicio, dt_final):
    # início do primeiro dia e fim do último, no fuso local
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime.combine(dt_inicio, time.min), tz),
            timezone.make_aware(datetime.combine(dt_final, time.max.replace(microsecond=0)), tz))


def normaliza_busca(busca):
    # mesma normalização de aspas feita por Termo.save, para comparar com o que está gravado
    return busca.strip().replace('“', '"').replace('”', '"').replace("'", '"')


def sincroniza_termos(projeto, termos, dtinicio, dtfinal, rede):
    """Ajusta os termos do projeto às linhas informadas; a identidade do termo é o texto da busca.

    Nunca exclui: termos que saíram são interrompidos ('X') e os que voltam são reativados.
    """
    linhas = list(dict.fromkeys(normaliza_busca(t) for t in termos if t.strip()))
    existentes = {}
    for termo in projeto.termo_set.order_by('pk'):
        existentes.setdefault(termo.busca.strip(), []).append(termo)

    ativos, reativados, novos = [], [], []
    for busca in linhas:
        grupo = existentes.get(busca, [])
        vigentes = [t for t in grupo if t.status != 'X']
        if vigentes:
            ativos.extend(vigentes)
        elif grupo:
            reativados.append(grupo[-1])
        else:
            novos.append(busca)

    removidos = [t.pk for busca, grupo in existentes.items() if busca not in linhas
                 for t in grupo if t.status != 'X']
    if removidos:
        Termo.objects.filter(pk__in=removidos).update(status='X')
        TermoStatus.objects.filter(termo_id__in=removidos, rede=rede).update(status='X')

    for termo in reativados:
        Termo.objects.filter(pk=termo.pk).update(status='A')
        if not TermoStatus.objects.filter(termo=termo, rede=rede).update(status='A'):
            TermoStatus.objects.create(termo=termo, rede=rede)

    pks = [t.pk for t in ativos + reativados]
    if pks:
        Termo.objects.filter(pk__in=pks).update(dtinicio=dtinicio, dtfinal=dtfinal)
    for busca in novos:
        termo = Termo.objects.create(projeto=projeto, busca=busca, dtinicio=dtinicio, dtfinal=dtfinal)
        TermoStatus.objects.create(termo=termo, rede=rede)


@login_required(login_url='/admin/login/')
def telegram_project(request):
    rede = Rede.objects.filter(nome__iexact='Telegram').first()
    if request.method == 'POST':
        form = TelegramProjectForm(request.POST, user=request.user)
        if not rede:
            messages.error(request, 'Rede Telegram não cadastrada. Contate o administrador.')
        elif form.is_valid():
            dados = form.cleaned_data
            dtinicio, dtfinal = periodo_coleta(dados['dt_inicio'], dados['dt_final'])
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


def projeto_editavel(user, pk):
    # projeto Telegram do próprio usuário; None se não existir, for de outro ou o pk não for numérico
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return None
    return Projeto.objects.filter(usuario=user, redes__nome__iexact='Telegram', pk=pk).distinct().first()


@login_required(login_url='/admin/login/')
def editar_projeto(request, pk):
    projeto = projeto_editavel(request.user, pk)
    if projeto is None:
        raise Http404
    rede = Rede.objects.filter(nome__iexact='Telegram').first()
    if request.method == 'POST':
        form = TelegramProjectForm(request.POST, user=request.user, projeto=projeto)
        if form.is_valid():
            dados = form.cleaned_data
            dtinicio, dtfinal = periodo_coleta(dados['dt_inicio'], dados['dt_final'])
            with transaction.atomic():
                projeto.nome = dados['nome']
                projeto.objetivo = dados['objetivo']
                projeto.lista_canais = dados['lista']
                projeto.save(update_fields=['nome', 'objetivo', 'lista_canais'])
                sincroniza_termos(projeto, dados['termos'], dtinicio, dtfinal, rede)
            messages.success(request, 'Projeto atualizado.')
            return redirect('painel')
    else:
        ativos = list(projeto.termo_set.exclude(status='X').order_by('pk'))
        inicios = [t.dtinicio for t in ativos]
        finais = [t.dtfinal for t in ativos if t.dtfinal]
        form = TelegramProjectForm(user=request.user, projeto=projeto, initial={
            'nome': projeto.nome, 'objetivo': projeto.objetivo, 'lista': projeto.lista_canais_id,
            'dt_inicio': timezone.localtime(min(inicios)).date() if inicios else None,
            'dt_final': timezone.localtime(max(finais)).date() if finais else None,
            'termos': '\n'.join(t.busca for t in ativos),
        })
        # ?lista=<id> (vindo da importação) substitui a lista atual se for uma opção válida do campo
        lista = request.GET.get('lista', '')
        if lista.isdigit() and form.fields['lista'].queryset.filter(pk=int(lista)).exists():
            form.initial['lista'] = int(lista)

    return render(request, 'telegram_project.html', {'form': form, 'projeto': projeto})


@login_required(login_url='/admin/login/')
def importar_lista(request):
    # ?projeto=<pk> (vindo da edição) é ignorado se não for um projeto editável pelo usuário
    projeto = projeto_editavel(request.user, request.GET.get('projeto'))
    voltar_url = reverse('editar_projeto', args=[projeto.pk]) if projeto else reverse('telegram_project')
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
                return redirect(f'{voltar_url}?lista={resultado["lista"].pk}')
    else:
        form = ImportListaForm(user=request.user)

    return render(request, 'importar_lista.html', {'form': form, 'voltar_url': voltar_url})


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


def query_sem_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


@login_required(login_url='/admin/login/')
def lista_canais(request):
    visiveis = listas_visiveis(request.user).annotate(total=Count('canais'))
    # ids inválidos ou de listas privadas alheias são descartados silenciosamente
    ids = []
    for valor in request.GET.getlist('lista'):
        if valor.isdigit() and int(valor) not in ids:
            ids.append(int(valor))
    listas = list(visiveis)
    validos = {lista.pk for lista in listas}
    ids = [i for i in ids if i in validos]

    def url_toggle(pk):
        novos = [i for i in ids if i != pk] if pk in ids else ids + [pk]
        if not novos:
            return reverse('lista_canais')
        return f'{reverse("lista_canais")}?{urlencode([("lista", i) for i in novos])}'

    itens = [{'id': lista.pk, 'nome': lista.nome, 'publica': lista.publica, 'total': lista.total,
              'selecionada': lista.pk in ids, 'url': url_toggle(lista.pk)} for lista in listas]
    selecionadas = [lista for lista in listas if lista.pk in ids]

    page_obj, total_canais, paginas, voltar_qs = None, 0, [], ''
    if selecionadas:
        canais = Canal.objects.filter(lista__in=selecionadas).distinct().order_by('-num_participantes', 'username')
        page_obj = Paginator(canais, 50).get_page(request.GET.get('page'))
        total_canais = page_obj.paginator.count
        paginas = paginas_visiveis(page_obj.number, page_obj.paginator.num_pages)
        voltar_qs = urlencode({'voltar': urlencode([('lista', i) for i in ids])})

    return render(request, 'lista_canais.html', {
        'listas': itens, 'tem_listas': bool(listas), 'selecionadas': selecionadas,
        'limpar_url': reverse('lista_canais'), 'importar_url': reverse('importar_lista'),
        'page_obj': page_obj, 'total_canais': total_canais, 'paginas': paginas,
        'query_sem_page': query_sem_page(request), 'voltar_qs': voltar_qs,
    })


@login_required(login_url='/admin/login/')
def canal_mensagens(request, pk):
    canal = get_object_or_404(Canal.objects.filter(lista__in=listas_visiveis(request.user)).distinct(), pk=pk)

    # só aceita voltar começando com "lista=" (evita open redirect)
    voltar = request.GET.get('voltar', '')
    if not voltar.startswith('lista='):
        voltar = ''
    voltar_url = reverse('lista_canais') + (f'?{voltar}' if voltar else '')

    form = FiltroMensagensForm(request.GET or None)
    estado, mensagens, pagina, paginas, termo, periodo = 'ok', [], None, [], '', None

    if canal.id_numerico is None:
        estado = 'nao_sincronizado'
    elif form.is_bound and not form.is_valid():
        estado = 'form_invalido'
    else:
        dados = form.cleaned_data if form.is_bound else {'por_pagina': 25}
        por_pagina = dados.get('por_pagina') or 25
        termo = dados.get('termo') or ''
        tz = timezone.get_current_timezone()
        inicio, final = dados.get('dt_inicio'), dados.get('dt_final')
        dt_inicio = timezone.make_aware(datetime.combine(inicio, time.min), tz) if inicio else None
        dt_final = timezone.make_aware(datetime.combine(final, time.max), tz) if final else None
        try:
            try:
                solicitada = max(int(request.GET.get('page', 1)), 1)
            except ValueError:
                solicitada = 1
            filtros = dict(dt_inicio=dt_inicio, dt_final=dt_final, termo=termo or None, limit=por_pagina)
            total, mensagens = busca_mensagens(canal.id_numerico, offset=(solicitada - 1) * por_pagina, **filtros)
            pagina = PaginaMensagens(solicitada, por_pagina, total)
            if pagina.number != solicitada:
                # página além da última (filtro mudou ou URL antiga): refaz na última
                total, mensagens = busca_mensagens(canal.id_numerico, offset=(pagina.number - 1) * por_pagina,
                                                   **filtros)
            paginas = pagina.paginas_visiveis
            if total == 0 and (inicio or final):
                # filtro de datas sem resultado: mostra o período que existe coletado
                periodo = periodo_canal(canal.id_numerico)
        except Exception:
            logger.exception('Erro ao consultar mensagens do canal %s no datalake', canal.pk)
            estado, mensagens, pagina, paginas = 'erro_datalake', [], None, []

    return render(request, 'canal_mensagens.html', {
        'canal': canal, 'form': form, 'estado': estado, 'mensagens': mensagens, 'pagina': pagina,
        'paginas': paginas, 'termo': termo, 'query_sem_page': query_sem_page(request),
        'voltar_url': voltar_url, 'voltar': voltar, 'periodo': periodo,
    })
