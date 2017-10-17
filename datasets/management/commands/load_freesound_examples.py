from django.core.management.base import BaseCommand
import json
from datasets.models import Dataset, Sound


class Command(BaseCommand):
    help = 'Load examples from json taxonomy file. Use it as python manage.py load_freesound_false_examples ' \
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

        failed_count = 0

        for d in data:
            node = taxonomy.get_element_at_id(d['id'])
            for ex_id in d['positive_examples_FS'][:2]:
                try:
                    sound = Sound.objects.get(freesound_id=ex_id)
                    node.freesound_examples.add(sound)
                except:
                    failed_count += 1
            for ex_id in d['positive_examples_FS'][2:]:
                try:
                    sound = Sound.objects.get(freesound_id=ex_id)
                    node.freesound_examples_verification.add(sound)
                except:
                    failed_count += 1
            node.save()

        print('{0} sounds did not exist'.format(failed_count))
