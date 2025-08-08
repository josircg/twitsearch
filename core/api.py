import json

from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Eixo, Projeto, Termo, Rede


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
    auth = request.headers.get('auth','')
    if not settings.AUTH_KEYS.get(auth):
        return HttpResponseForbidden()

    termos = []
    for termo in Termo.objects.filter(projeto__redes=rede_id).exclude(projeto__status='C').order_by('projeto'):
        termos.append({
            'projeto_id': termo.projeto.id,
            'projeto_nome': termo.projeto.nome,
            'projeto_index': termo.projeto.prefix,
            'id': termo.id,
            'nome': termo.descritivo,
            'busca': termo.busca,
            'busca_complementar': termo.busca_complementar,
            'idioma': termo.language,
            'status': termo.status if termo.projeto.status == 'A' else termo.projeto.status
        })

    return HttpResponse(json.dumps(termos), content_type='application/json')


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