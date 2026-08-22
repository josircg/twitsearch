import csv
from io import StringIO

import openpyxl

from django.contrib import messages
from django.shortcuts import render
from .forms import ImportForm


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


def importacao_arquivo(request):
    if request.method == 'POST':
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            arquivo = request.FILES.get('arquivo')
            lista = request.POST.get('lista')
            categoria = request.POST.get('categoria')
            try:
                if arquivo:
                    if arquivo.name.lower().endswith('.csv'):
                        result = import_csv(arquivo)
                    else:
                        result = import_xlsx(arquivo)
                    messages.info(request, result)
                else:
                    messages.error(request, 'Nenhum arquivo enviado. Tente utilizar outro navegador.')

            except Exception as e:
                message = ''.join(traceback.TracebackException.from_exception(e).format())
                print(message)
                # sendmail('Erro Importação Lattes', [settings.REPLY_TO_EMAIL], message=message)
                messages.error(request, 'Houve um erro durante a importação. Já estamos averiguando o problema')

            return redirect('importacao_arquivo')
    else:
        form = ImportForm()

    return render(request, 'core/import_tweets.html', {'form': form, })

