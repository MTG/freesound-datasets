from django.core.management.base import BaseCommand
from datasets.tasks import refresh_sound_extra_data


class Command(BaseCommand):
    help = 'Refresh the extra_data field in Sound model' \


    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        refresh_sound_extra_data()
