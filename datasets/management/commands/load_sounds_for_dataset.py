from django.core.management.base import BaseCommand
from datasets.models import *
import sys
import json


class Command(BaseCommand):
    help = 'Populates a dataset with information given in a json file. ' \
           'Use like python manage.py load_sounds_for_dataset short_ds_name filepath.json algorithm_name'

    def add_arguments(self, parser):
        parser.add_argument('dataset_short_name', type=str)
        parser.add_argument('filepath', type=str)
        parser.add_argument('algorithm_name', type=str)

    def handle(self, *args, **options):
        file_location = options['filepath']
        dataset_short_name = options['dataset_short_name']
        algorithm_name = options['algorithm_name']
        dataset = Dataset.objects.get(short_name=dataset_short_name)
        print('Loading data...')
        data = json.load(open(file_location))

        for count, (sound_id, sound_data) in enumerate(data.items()):
            sys.stdout.write('\rCreating sound %i of %i (%.2f%%)' % (count + 1, len(data),
                                                                    100.0 * (count + 1) / len(data)))
            sys.stdout.flush()

            try:
                Sound.objects.get(freesound_id=sound_id)
            except Sound.DoesNotExist:
                # If does not yet exist, create it :)

                sound, _ = Sound.objects.get_or_create(
                    name=sound_data['name'][:200],
                    freesound_id=sound_id,
                    extra_data={
                        'tags': sound_data['tags'],
                    }
                )
                sound_dataset, _ = SoundDataset.objects.get_or_create(
                    dataset=dataset,
                    sound=sound
                )

                for node_id in sound_data['aso_ids']:
                    Annotation.objects.create(
                        sound_dataset=sound_dataset,
                        type='AU',
                        algorithm=algorithm_name,
                        value=node_id
                    )
