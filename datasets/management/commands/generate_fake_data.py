from django.core.management.base import BaseCommand
from datasets.models import *
from django.contrib.auth.models import User
from django.db import transaction
import random


VALID_FS_IDS = [384240, 384239, 384238, 384237, 384218, 384217, 384211, 384210, 384206, 384202, 384201, 384200, 384199, 384198, 384197, 384196, 384195, 384193, 384192, 384191, 384190, 384188, 384187, 384186, 384185, 384184, 384183, 384182, 384181, 384180, 384179, 384178, 384177, 384176, 384175, 384174, 384173, 384172, 384171, 384170, 384169, 384168, 384167, 384166, 384165, 384164, 384163, 384162, 384161, 384160, 384159, 384158, 384157, 384156, 384155, 384154, 384153, 384152, 384151, 384150, 384149, 384148, 384147, 384146, 384145, 384144, 384143, 384142, 384141, 384140, 384139, 384138, 384137, 384136, 384135, 384134, 384133, 384132, 384131, 384130, 384129, 384128, 384127, 384126, 384125, 384124, 384123, 384122, 384121, 384120, 384119, 384118, 384117, 384116, 384115, 384114, 384113, 384112, 384111, 384110, 384109, 384107, 384106, 384105, 384104, 384103, 384102, 384101, 384100, 384099, 384098, 384097, 384096, 384095, 384094, 384093, 384092, 384091, 384090, 384089, 384088, 384087, 384086, 384085, 384084, 384083, 384082, 384081, 384080, 384079, 384078, 384077, 384076, 384075, 384074, 384073, 384072, 384071, 384070, 384069, 384068, 384067, 384066, 384065, 384064, 384063, 384062, 384061, 384060, 384059, 384058, 384057, 384056, 384055, 384054, 384053, 384052, 384051, 384050, 384049, 384048, 384047, 384046, 384045, 384044, 384043, 384042, 384041, 384040, 384038, 384037, 384036, 384035, 384034, 384033, 384032, 384031, 384030, 384029, 384028, 384027, 384026, 384025, 384024, 384023, 384022, 384021, 384020, 384019, 384018, 384017, 384016, 384015, 384014, 384013, 384012, 384011, 384010, 384009, 384008]

def get_dataset(dataset_short_name):
    """Get Dataset object instance.
    
    Args:
        dataset_short_name: A string for the short name of the dataset.
    
    Returns:
        A Dataset object instance with the short name given as argument.
    
    Raises:
        Exception: The short name given does not correspond to an existing dataset.
    """
    try:
        return Dataset.objects.get(short_name=dataset_short_name)
    except Dataset.DoesNotExist:
        raise Exception("Can't create fake data as dataset with short name {0} does not seem to exist. Did you load the initial.json fixture?".format(short_name))

def create_sounds(dataset_short_name, num_sounds):
    """Create fake Sound object instances.
    
    Create fake sounds to the dataset instance with the specified short name.
    
    Args:
        dataset_short_name: A string corresponding to the short name of the dataset to which the sounds will be added.
        num_sounds: An integer corresponding to the number of fake sounds to create.
    """
    dataset = get_dataset(dataset_short_name)

    # Create sounds and add them to dataset
    print('Generating {0} fake sounds...'.format(num_sounds))
    num_current_sounds = Sound.objects.all().count()
    fsids = [VALID_FS_IDS[i % len(VALID_FS_IDS)] for i in range(0, num_sounds)]
    with transaction.atomic():
        for count, fsid in enumerate(fsids):
            sound = Sound.objects.create(
                name='Freesound sound #{0}'.format(count + num_current_sounds),
                freesound_id=fsid,
            )
            SoundDataset.objects.create(
                dataset=dataset,
                sound=sound
            )

def create_users(num_users):
    """Create fake User object instances.
    
    Args:
        num_users: An integer corresponding to the number of fake users to create.
    """
    print('Generating {0} fake users...'.format(num_users))
    num_current_users = User.objects.all().count()
    with transaction.atomic():
        for i in range(0, num_users):
            User.objects.create_user(
                username='username_{0}'.format(i + num_current_users),
                password='123456'
            )

def create_annotations(dataset_short_name, num_annotations):
    """Create fake Annotation object instances.
    
    Create fake annotations to random sound in the dataset instance with the specified short name.
    
    Args:
        dataset_short_name: A string corresponding to the short name of the dataset to which the annotations will be added.
        num_annotations: An integer corresponding to the number of fake annotations to create.
    """
    # Get the dataset, sound object ids, annotation object ids
    dataset = get_dataset(dataset_short_name)
    all_sounddataset_object_ids = SoundDataset.objects.all().values_list('id', flat=True)
    all_user_object_ids = User.objects.all().values_list('id', flat=True)

    print('Generating {0} fake annotations...'.format(num_annotations))
    possible_fake_annotation_values = [node['id'] for node in dataset.taxonomy.get_all_nodes()]
    with transaction.atomic():
        for i in range(0, num_annotations):
            Annotation.objects.create(
                sound_dataset_id=random.choice(all_sounddataset_object_ids),
                type='AU',
                algorithm='Fake algorithm name',
                value=random.choice(possible_fake_annotation_values),
                created_by_id=random.choice(all_user_object_ids),
            )

def create_votes(num_votes):
    """Create fake Votes object instances.
    
    Create fake votes to random annotations.
    
    Args:
        num_votes: An integer corresponding to the number of fake votes to create.
    """
    # Get annotation object ids, user object ids
    all_annotation_object_ids = Annotation.objects.all().values_list('id', flat=True)
    all_user_object_ids = User.objects.all().values_list('id', flat=True)

    # Add votes for annotations
    print('Generating {0} fake annotation votes...'.format(num_votes))
    possible_vote_options = [-1, 1, 1, 1]  # Bias towards positive votes
    with transaction.atomic():
        for i in range(0, num_votes):
            Vote.objects.create(
                annotation_id=random.choice(all_annotation_object_ids),
                vote=random.choice(possible_vote_options),
                created_by_id=random.choice(all_user_object_ids),
            )


class Command(BaseCommand):
    help = 'Generates fake Sounds, Annotations and Votes data. ' \
           'Usage: python manage.py generate_fake_data fsd 100 5 1000 2000'

    def add_arguments(self, parser):
        parser.add_argument('dataset_short_name', type=str)
        parser.add_argument('num_sounds', type=int)
        parser.add_argument('num_users', type=int)
        parser.add_argument('num_annotations', type=int)
        parser.add_argument('num_votes', type=int)

    def handle(self, *args, **options):
        short_name = options['dataset_short_name']
        num_sounds = options['num_sounds']
        num_users = options['num_users']
        num_annotations = options['num_annotations']
        num_votes = options['num_votes']

        create_sounds(short_name, num_sounds)
        create_users(num_users)
        create_annotations(short_name, num_annotations)
        create_votes(num_votes)
