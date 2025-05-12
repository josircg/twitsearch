import json

from django.http import HttpResponse
from .models import Projeto, Termo, Rede


def redes(request):
    result = Rede.objects.all().values('id', 'nome', 'ativa')
    return HttpResponse(json.dumps(list(result)), content_type='application/json')


def projetos(request, status=None):
    result = []
    if status:
        dataset = Projeto.objects.filter(status=status)
    else:
        dataset = Projeto.objects.all()
    for projeto in dataset.order_by('id'):
        result.append({'id': projeto.id,
                       'nome': projeto.nome,
                       'redes': list(projeto.redes.all().values('id')),
                       'status': projeto.get_status_display(),
                       })

    return HttpResponse(json.dumps(result), content_type='application/json')


def termos(request, rede_id):
    termos = []
    for termo in Termo.objects.filter(projeto__redes=rede_id).order_by('projeto'):
        termos.append({
            'id': termo.id,
            'projeto': termo.projeto.id,
            'nome': termo.descritivo,
            'busca': termo.busca,
            'status': termo.get_status_display()
        })

    return HttpResponse(json.dumps(termos), content_type='application/json')