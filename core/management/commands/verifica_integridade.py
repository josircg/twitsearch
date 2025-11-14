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
                tot_registros__gt=1000,
            )
            .values('termo')
            .annotate(qtd=Count('id'))
        )

        if termos_erro > 0 or duplicados.exists() or resultado.exists():
            # Prepare email content
            subject = "[CAPITU] Integridade dos Monitoramentos"
            body = []

            if termos_erro > 0:
                body.append(
                    f"Termos com erro: {termos_erro}.<br>Verique em: https://capitu.minerva.ibict.br/admin/core/termo/?status__exact=E\n"
                )

            if duplicados.exists():
                body.append("Excesso de agendamento para os termos abaixo:\n")
                for ag in duplicados:
                    body.append(f"https://capitu.minerva.ibict.br/admin/core/termo/{ag.termo_id}/\n")

            if resultado:
                body.append("Capturas com volume excessivo de dados:\n")
                for r in resultado:
                    body.append(f"https://capitu.minerva.ibict.br/admin/core/termo/{r['termo']}/\n")            

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
