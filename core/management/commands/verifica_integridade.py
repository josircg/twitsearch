'''
Informa por email situações de erro durante a captura dos dados do Twitter
Josir 08/2025

* Erros de comunicação: O Twitter travou a captura por algum erro interno da API. Quando isso ocorre, o termo é
  marcado com Erro para notificar os analistaas de que o problema ocorreu.

* Erros de agendamento: O agendamento ocorre quando uma captura (crawler na API) estoura o limite de tweets
  (5000 por default). Esse limite é necessário para que a captura de um único projeto não trave todos os demais
  projetos. Nesse caso, o crawler cria um agendamento para que o processo continue de onde parou.

  Entretanto, pode ocorrer casos em que o número de agendamentos podem ficar recorrentes, ou seja, um
  agendamento criar um novo agendamento pois ele próprio estourou o limite de 5000.
'''
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from core.models import PROC_FULL, Agendamento, Processamento, Termo
from utils.email import send_message_email


class Command(BaseCommand):
    help = 'Verifica a integridade dos monitoramentos agendados'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS(
            "Iniciando verificação de integridade..."
        ))
        
        termos_erro = Termo.objects.filter(status__exact='E').count()

        processamentos_com_erro = Processamento.objects.filter(status=Processamento.Status.ERRO).count()

        duplicados = Agendamento.objects.filter(
            status=Agendamento.Status.AGENDADO
        ).filter(
            termo_id__in=Agendamento.objects.filter(
                status=Agendamento.Status.AGENDADO
            ).values('termo').annotate(qtd=Count('id')).filter(qtd__gt=1).values('termo')
        )
                
        agora = timezone.now()
        limite = agora - timezone.timedelta(hours=24)

        resultado = (
            Processamento.objects
            .filter(
                tipo=PROC_FULL,
                dt__gte=limite,
                tot_registros__gt=3000,
            )
            .values('termo')
            .annotate(qtd=Count('id'))
        )

        if termos_erro > 0 or processamentos_com_erro > 0 or duplicados.exists() or resultado.exists():
            # Prepare email content
            subject = "[CAPITU] Integridade dos Monitoramentos"
            body = []

            if termos_erro > 0:
                body.append(
                    f"Termos com erro: {termos_erro}.<br>"
                    f"Verique em: https://capitu.minerva.ibict.br/admin/core/termo/?status__exact=E\n"
                )

            if processamentos_com_erro > 0:
                body.append(
                    f"Processamentos com erro: {processamentos_com_erro}.<br>"
                    f"Verique em: https://capitu.minerva.ibict.br/admin/core/processamento/?status__exact=E"
                )

            if duplicados.exists():
                body.append("Excesso de agendamento para os termos abaixo:")
                for ag in duplicados:
                    body.append(f"https://capitu.minerva.ibict.br/admin/core/termo/{ag.termo_id}/")

            if resultado:
                body.append("Capturas com volume excessivo de dados:")
                for r in resultado:
                    body.append(f"https://capitu.minerva.ibict.br/admin/core/termo/{r['termo']}/")

            message = "<br>".join(body)

            send_message_email(
                subject,
                message=message,
                recipient_list=[admin[1] for admin in settings.ADMINS],                
            )
                        
        self.stdout.write(self.style.SUCCESS(
            """
Verificação de integridade concluída com sucesso!
Termos com erro: {}.
Agendamentos duplicados: {}.
Capturas com volume excessivo de dados: {}.""".format(
                termos_erro,
                duplicados.count(),
                resultado.count()
            )
        ))
