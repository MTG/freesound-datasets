from django.core.management.base import BaseCommand
from datasets.models import *
import json
from datasets.models import Taxonomy, Dataset


class Command(BaseCommand):
    help = 'Update the taxonomy from json file. Use it as python manage.py update_taxonomy ' \
           'TAXONOMY_ID PATH/TO/TAOXNOMY_FILE.json'

    def add_arguments(self, parser):
        parser.add_argument('taxonomy_id', type=int)
        parser.add_argument('taxonomy_file', type=str)

    def handle(self, *args, **options):
        file_location = options['taxonomy_file']
        taxonomy_id = options['taxonomy_id']

        data = json.load(open(file_location))

        prepared_data = {}
        parents = collections.defaultdict(list)
        for d in data:
            for cid in d['child_ids']:
                parents[cid].append(d['id'])
            prepared_data[d['id']] = d
        for childid, parentids in parents.items():
            prepared_data[childid]['parent_ids'] = parentids

        taxonomy = Taxonomy.objects.get(id=taxonomy_id)
        taxonomy.data = prepared_data
        taxonomy.save()

