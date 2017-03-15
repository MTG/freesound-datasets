from django.core.management.base import BaseCommand
from datasets.models import *
import random

VALID_FS_IDS = [384240, 384239, 384238, 384237, 384218, 384217, 384211, 384210, 384206, 384202, 384201, 384200, 384199, 384198, 384197, 384196, 384195, 384193, 384192, 384191, 384190, 384188, 384187, 384186, 384185, 384184, 384183, 384182, 384181, 384180, 384179, 384178, 384177, 384176, 384175, 384174, 384173, 384172, 384171, 384170, 384169, 384168, 384167, 384166, 384165, 384164, 384163, 384162, 384161, 384160, 384159, 384158, 384157, 384156, 384155, 384154, 384153, 384152, 384151, 384150, 384149, 384148, 384147, 384146, 384145, 384144, 384143, 384142, 384141, 384140, 384139, 384138, 384137, 384136, 384135, 384134, 384133, 384132, 384131, 384130, 384129, 384128, 384127, 384126, 384125, 384124, 384123, 384122, 384121, 384120, 384119, 384118, 384117, 384116, 384115, 384114, 384113, 384112, 384111, 384110, 384109, 384107, 384106, 384105, 384104, 384103, 384102, 384101, 384100, 384099, 384098, 384097, 384096, 384095, 384094, 384093, 384092, 384091, 384090, 384089, 384088, 384087, 384086, 384085, 384084, 384083, 384082, 384081, 384080, 384079, 384078, 384077, 384076, 384075, 384074, 384073, 384072, 384071, 384070, 384069, 384068, 384067, 384066, 384065, 384064, 384063, 384062, 384061, 384060, 384059, 384058, 384057, 384056, 384055, 384054, 384053, 384052, 384051, 384050, 384049, 384048, 384047, 384046, 384045, 384044, 384043, 384042, 384041, 384040, 384038, 384037, 384036, 384035, 384034, 384033, 384032, 384031, 384030, 384029, 384028, 384027, 384026, 384025, 384024, 384023, 384022, 384021, 384020, 384019, 384018, 384017, 384016, 384015, 384014, 384013, 384012, 384011, 384010, 384009, 384008]


class Command(BaseCommand):
    help = 'Generates fake Sounds, Annotations and Votes data'

    def handle(self, *args, **options):

        # Get the dataset
        try:
            dataset = Dataset.objects.get(name='FreesoundDataset')
        except Dataset.DoesNotExist:
            raise Exception('Can\'t create fake data as FreesoundDataset does not seem to exist. '
                            'Did you load the initial.json fixture?')

        # Create sounds and add them to dataset
        num_current_sounds = Sound.objects.all().count()
        for count, fsid in enumerate(VALID_FS_IDS):
            sound, _ = Sound.objects.get_or_create(
                name='Freesound sound #{0}'.format(count + num_current_sounds),
                freesound_id=fsid,
            )
            SoundDataset.objects.get_or_create(
                dataset=dataset,
                sound=sound
            )

        # Create annotations
        possible_fake_annotation_values = [node['id'] for node in dataset.taxonomy.get_all_nodes()]
        for i in range(0, 1000):
            sound_dataset = random.choice(list(SoundDataset.objects.all()))
            Annotation.objects.create(
                sound_dataset=sound_dataset,
                type='AU',
                algorithm='Fake algorithm name',
                value=random.choice(possible_fake_annotation_values)
            )

        # Add votes for annotations
        possible_vote_options = [-1, 1]
        for i in range(0, 3000):
            annotation = random.choice(list(Annotation.objects.all()))
            Vote.objects.create(
                annotation=annotation,
                vote=random.choice(possible_vote_options)
            )
