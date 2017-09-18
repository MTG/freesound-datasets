from django.core.management.base import BaseCommand
from datasets.tasks import refresh_sound_deleted_state


class Command(BaseCommand):
    help = 'Refresh the deleted_in_freesound field in Sound model' \


    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        refresh_sound_deleted_state()
