from django.core.management.base import BaseCommand


class Command(BaseCommand):
    label = 'Teste Management'

    def handle(self, *args, **options):
        print(self.label)

