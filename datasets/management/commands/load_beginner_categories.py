from django.core.management.base import BaseCommand
import json
from datasets.models import Dataset, TaxonomyNode


class Command(BaseCommand):
    help = 'Load field easy categories from json taxonomy file. ' \
           'Use it as python manage.py load_beginner_categories.py ' \
           'DATASET_ID PATH/TO/TAOXNOMY_FILE.json'

    def add_arguments(self, parser):
        parser.add_argument('dataset_id', type=int)
        parser.add_argument('taxonomy_file', type=str)

    def handle(self, *args, **options):
        file_location = options['taxonomy_file']
        dataset_id = options['dataset_id']

        ds = Dataset.objects.get(id=dataset_id)
        taxonomy = ds.taxonomy
        data = json.load(open(file_location))

        for d in data:
            node = taxonomy.get_element_at_id(d['id'])
            if d['beginner_category']:
                node.beginner_task = True
            else:
                node.beginner_task = False
            node.save()
