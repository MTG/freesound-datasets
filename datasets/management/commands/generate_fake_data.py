from django.core.management.base import BaseCommand
from datasets.models import *
import random


class Command(BaseCommand):
    help = 'Generates fake Dataset, Sound, Annotations and Votes data'

    def handle(self, *args, **options):

        # Create a fake dataset
        dataset, _ = Dataset.objects.get_or_create(
            name='A fake dataset',
            short_name='fsd',
            description='A textual description for the fake dataset',
        )

        # Create sounds and add them to dataset
        for i in range(0, 100):
            sound, _ = Sound.objects.get_or_create(
                name='Fake sound #{0}'.format(i),
                freesound_id=1234 + i,
            )
            SoundDataset.objects.get_or_create(
                dataset=dataset,
                sound=sound
            )

        # Create annotations
        possible_fake_annotations = ['/m/0z9c', '/m/07q2z82', '/m/0mkg', '/t/dd00093', '/m/042v_gx']
        try:
            taxonomy = dataset.taxonomy
            possible_fake_annotations = [node['id'] for node in dataset.taxonomy.get_all_nodes()]
        except:
            pass

        for i in range(0, 500):
            sound_dataset = random.choice(list(SoundDataset.objects.all()))
            annotation, _ = Annotation.objects.get_or_create(
                sound_dataset=sound_dataset,
                type='AU',
                algorithm='Fake algorithm name',
                value=random.choice(possible_fake_annotations)
            )

        # Add votes for annotations
        possible_vote_options = [-1, 1]
        for i in range(0, 1000):
            annotation = random.choice(list(Annotation.objects.all()))
            vote, _ = Vote.objects.get_or_create(
                annotation=annotation,
                vote=random.choice(possible_vote_options)
            )
