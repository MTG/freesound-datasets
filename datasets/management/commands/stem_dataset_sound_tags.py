from django.core.management.base import BaseCommand
from datasets.tasks import stem_dataset_sound_tags


class Command(BaseCommand):
    help = 'Apply Porter Stemming to all sound tags and add it to extra_data.stemmed_tags'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        stem_dataset_sound_tags()
