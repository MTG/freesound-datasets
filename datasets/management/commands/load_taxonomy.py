from django.core.management.base import BaseCommand
from datasets.models import *
import json
from datasets.models import Taxonomy, Dataset


class Command(BaseCommand):
    help = 'Load and prepare a taxonomy from json file. Use it as python manage.py load_taxonomy ' \
           'DATASET_ID PATH/TO/TAOXNOMY_FILE.json'

    def add_arguments(self, parser):
        parser.add_argument('dataset_id', type=int)
        parser.add_argument('taxonomy_file', type=str)

    def handle(self, *args, **options):
        file_location = options['taxonomy_file']
        dataset_id = options['dataset_id']

        ds = Dataset.objects.get(id=dataset_id)
        data = json.load(open(file_location))

        prepared_data = {}
        parents = collections.defaultdict(list)
        for d in data.values():
            for cid in d.get('child_ids', []):
                parents[cid].append(d['id'])
            prepared_data[d['id']] = d
        for childid, parentids in parents.items():
            prepared_data[childid]['parent_ids'] = parentids

        tx = Taxonomy.objects.create(data=prepared_data)
        ds.taxonomy = tx
        ds.save()
