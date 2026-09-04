import json

from django.http import HttpResponse, HttpResponseForbidden, HttpRequest
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from .models import Eixo, Projeto, Termo, Rede, Processamento, TermoStatus
from telegram.models import Canal


def redes(request):
    result = Rede.objects.all().values('id', 'nome', 'ativa')
    return HttpResponse(json.dumps(list(result)), content_type='application/json')


def eixos(request):
    auth = request.headers.get('auth','')
    if not settings.AUTH_KEYS.get(auth):
        return HttpResponseForbidden()

    result = Eixo.objects.all().values('id', 'nome', 'descricao')
    return HttpResponse(json.dumps(list(result)), content_type='application/json')


def projetos(request, status=None):

    auth = request.headers.get('auth','')
    if not settings.AUTH_KEYS.get(auth):
        return HttpResponseForbidden()

    result = []
    if status:
        dataset = Projeto.objects.filter(status=status)
    else:
        dataset = Projeto.objects.all()
    for projeto in dataset.order_by('id'):
        result.append({'id': projeto.id,
                       'nome': projeto.nome,
                       'redes': list(projeto.redes.all().values('id')),
                       'eixo': projeto.eixo.nome,
                       'status': projeto.get_status_display(),
                       })

    return HttpResponse(json.dumps(result), content_type='application/json')


def termos(request, rede_id):
    #auth = request.headers.get('auth','')
    #if not settings.AUTH_KEYS.get(auth):
    #    return HttpResponseForbidden()

    lista = []
    for termo in Termo.objects.filter(projeto__redes=rede_id).exclude(projeto__status='C').order_by('projeto'):
        # se for telegram, gerar a lista de canais
        if rede_id == 4:
            if termo.projeto.lista_canais:
                canais = list(termo.projeto.lista_canais.canais.filter(
                    id_numerico__isnull=False, status='A').values_list('username', flat=True))
                status_record = TermoStatus.objects.filter(termo=termo, rede_id=rede_id).first()
                if status_record:
                    ult_processo = status_record.ult_processo
                    status = status_record.status
                else:
                    ult_processo = None
                    status = 'I'
            else:
                # se não tem canais, não realiza o procesamento do Telegram
                status = 'X'
        else:
            canais = None
            ult_processo = None
            status = termo.status if termo.projeto.status == 'A' else termo.projeto.status

        dtinicio = termo.dtinicio.strftime('%Y-%m-%d')
        dtfinal = termo.dtfinal.strftime('%Y-%m-%d') if termo.dtfinal else None

        if status != 'X':
            lista.append({
                'projeto_id': termo.projeto.id,
                'projeto_nome': termo.projeto.nome,
                'projeto_index': termo.projeto.prefix,
                'id': termo.id,
                'nome': termo.descritivo,
                'busca': termo.busca,
                'busca_complementar': termo.busca_complementar,
                'idioma': termo.language,
                'dtinicio': dtinicio,
                'dtfinal': dtfinal,
                'canais': canais,
                'status': status,
                'ult_processo': ult_processo
            })

    return HttpResponse(json.dumps(lista), content_type='application/json')


def termos_by_id(request, termo_id):
    auth = request.headers.get('auth','')
    if not settings.AUTH_KEYS.get(auth):
        return HttpResponseForbidden()
    
    termo = get_object_or_404(Termo, id=termo_id)
    termo_data = {
        'projeto_id': termo.projeto.id,
        'projeto_nome': termo.projeto.nome,
        'projeto_index': termo.projeto.prefix,
        'id': termo.id,
        'nome': termo.descritivo,
        'busca': termo.busca,
        'busca_complementar': termo.busca_complementar,
        'idioma': termo.language,
        'status': termo.status if termo.projeto.status == 'A' else termo.projeto.status
    }
    
    return HttpResponse(json.dumps(termo_data), content_type='application/json')


def processo(request, processo_id):
    auth = request.headers.get('auth','')
    if not settings.AUTH_KEYS.get(auth):
        return HttpResponseForbidden()
    objeto = get_object_or_404(Processamento, id=processo_id)
    record = {'dt': str(objeto.dt), 'count': objeto.tot_registros,
              'tipo': objeto.get_tipo_display(),
              'status': objeto.get_status_display()}
    return HttpResponse(json.dumps(record), content_type='application/json')


def canais_telegram(request: HttpRequest):
    lista = []
    for canal in Canal.objects.filter(status=Canal.Status.ATIVO):
        record = {'channel': canal.username, 'id': canal.id_numerico, 'access_hash': canal.access_hash}
        lista.append(record)
    return HttpResponse(json.dumps(lista), content_type='application/json')


def processo_rede_get(request: HttpRequest, termo_id: int, rede_id: int):
    record = TermoStatus.objects.filter(termo_id=termo_id, rede_id=rede_id).first()
    if record:
        result = record.ult_processo or 0
    else:
        result = 0
    return HttpResponse(json.dumps(result), content_type='application/json')


# atualiza o ult_processo a partir do último registro processado no datalake
# quando processo for 'E', deve-se registrar que o processamento não foi bem sucedido
# A API retorna o status do Termo para a rede indicada.
@csrf_exempt
def processo_rede_set(request: HttpRequest, termo_id: int, rede_id: int, processo: str):
    # auth = request.headers.get('auth', '')
    # if not settings.AUTH_KEYS.get(auth):
    #     return HttpResponseForbidden()
    record, _ = TermoStatus.objects.get_or_create(termo_id=termo_id, rede_id=rede_id, defaults={'ult_processo': 0})
    if processo == 'E':
        record.status = 'E'
    else:
        record.ult_processo = int(processo)
        record.status = 'A'
    record.save()
    return HttpResponse(json.dumps(record.status), content_type='application/json')

