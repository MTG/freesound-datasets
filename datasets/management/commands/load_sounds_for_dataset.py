from django.core.management.base import BaseCommand
from datasets.models import *
from django.db import transaction
import sys
import json


def chunks(l, n):
    """Yield successive ``n``-sized chunks from ``l``.
    Examples:
        >>> chunks([1, 2, 3, 4, 5], 2) #doctest: +ELLIPSIS
        <generator object chunks at 0x...>
        >>> list(chunks([1, 2, 3, 4, 5], 2))
        [[1, 2], [3, 4], [5]]
    """
    for i in range(0, len(l), n):
        yield l[i:i+n]


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

        count = 0
        # Iterate all the sounds in chunks so we can do all transactions of a chunk atomically
        for chunk in chunks(list(data.keys()), 5000):
            with transaction.atomic():
                for sound_id in chunk:
                    sound_data = data[sound_id]
                    count += 1
                    sys.stdout.write('\rCreating sound %i of %i (%.2f%%)'
                                     % (count + 1, len(data), 100.0 * (count + 1) / len(data)))
                    sys.stdout.flush()
                    sound = Sound.objects.create(
                        name=sound_data['name'][:200],
                        freesound_id=sound_id,
                        extra_data={
                            'tags': sound_data['tags'],
                            'duration': sound_data['duration'],
                            'username': sound_data['username'],
                            'license': sound_data['license'],
                            'description': sound_data['description'],
                            'previews': sound_data['previews'],
                            'analysis': sound_data['analysis'] if 'analysis' in sound_data.keys() else {},
                        }
                    )
                    sound_dataset = SoundDataset.objects.create(
                        dataset=dataset,
                        sound=sound
                    )

                    for node_id in sound_data['aso_ids']:
                        CandidateAnnotation.objects.create(
                            sound_dataset=sound_dataset,
                            type='AU',
                            algorithm=algorithm_name,
                            value=node_id
                        )
