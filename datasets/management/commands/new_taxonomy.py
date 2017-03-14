from django.core.management.base import BaseCommand
from datasets.models import *
import json
import random

from datasets.models import Taxonomy, Dataset

class Command(BaseCommand):
    help = 'Create new taxonomy from json file'

    def add_arguments(self, parser):
        parser.add_argument('dataset_id', type=int)
        parser.add_argument('taxonomy_file', type=str)

    def handle(self, *args, **options):
        file_location = options['taxonomy_file']
        dataset_id = options['dataset_id']

        ds = Dataset.objects.get(id=dataset_id)
        data = json.load(open(file_location))
        tx = Taxonomy.objects.create(data=data)
        ds.taxonomy = tx
        ds.save()
