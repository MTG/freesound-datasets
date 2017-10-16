from datasets.models import Dataset, DatasetRelease, Annotation, Vote, TaxonomyNode, Sound
from django.db.models import Count
from django.contrib.auth.models import User
from django.db import transaction
from celery import shared_task
from django.utils import timezone
from utils.redis_store import store
from datasets.templatetags.dataset_templatetags import calculate_taxonomy_node_stats
from datasets.utils import query_freesound_by_id
import json
import math
import logging
import datetime

logger = logging.getLogger('tasks')


@shared_task
def generate_release_index(dataset_id, release_id, max_sounds=None):
    dataset = Dataset.objects.get(id=dataset_id)
    dataset_release = DatasetRelease.objects.get(id=release_id)

    # Get sounds' info and annotations
    sounds_info = list()
    n_sounds = 0
    n_annotations = 0
    n_validated_annotations = 0
    node_set = set()
    sounds = dataset.sounds.all()[:max_sounds]
    for count, sound in enumerate(sounds):
        annotations = sound.get_annotations(dataset)
        if annotations:
            annotation_values = [item.value for item in annotations]
            sounds_info.append((
                sound.id, annotation_values
            ))
            node_set.update(annotation_values)
            n_sounds += 1
            n_annotations += annotations.count()
            n_validated_annotations += annotations.annotate(num_votes=Count('votes')).filter(num_votes__lt=0).count()
        if count % 50:
            # Every 50 sounds, update progress
            dataset_release.processing_progress = int(math.floor(count * 100.0 / len(sounds)))
            dataset_release.processing_last_updated = timezone.now()
            dataset_release.save()

    # Make data structure
    release_data = {
       'meta': {
           'dataset': dataset.name,
           'release': dataset_release.release_tag,
           'num_sounds': n_sounds,
           'num_taxonomy_nodes': len(node_set),
           'num_annotations': n_annotations,
           'num_validated_annotations': n_validated_annotations
       },
       'sounds_info': sounds_info,
    }

    # Save release data to file
    json.dump(release_data, open(dataset_release.index_file_path, 'w'))

    # Update dataset_release object
    dataset_release.num_validated_annotations = n_validated_annotations
    dataset_release.num_annotations = n_annotations
    dataset_release.num_sounds = n_sounds
    dataset_release.num_nodes = len(node_set)
    dataset_release.processing_progress = 100
    dataset_release.processing_last_updated = timezone.now()
    dataset_release.is_processed = True
    dataset_release.save()


@shared_task
def compute_dataset_basic_stats(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        store.set(store_key, {
            'num_taxonomy_nodes': dataset.taxonomy.get_num_nodes(),
            'num_sounds': dataset.num_sounds,
            'num_annotations': dataset.num_annotations,
            'avg_annotations_per_sound': dataset.avg_annotations_per_sound,
            'percentage_validated_annotations': dataset.percentage_validated_annotations,
            'num_ground_truth_annotations': dataset.num_ground_truth_annotations,
            'num_verified_annotations': dataset.num_verified_annotations,
            'num_user_contributions': dataset.num_user_contributions
        })
        logger.info('Finished computing data for {0}'.format(store_key))
    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_dataset_taxonomy_stats(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        node_ids = dataset.taxonomy.get_all_node_ids()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                    SELECT taxonomynode.node_id
                           , COUNT(annotation.id)
                           , COUNT(DISTINCT(sound.id))
                        FROM datasets_annotation annotation
                  INNER JOIN datasets_sounddataset sounddataset
                          ON annotation.sound_dataset_id = sounddataset.id
                  INNER JOIN datasets_sound sound
                          ON sound.id = sounddataset.sound_id
                  INNER JOIN datasets_taxonomynode taxonomynode
                          ON taxonomynode.id = annotation.taxonomy_node_id
                       WHERE taxonomynode.node_id IN %s
                         AND sounddataset.dataset_id = %s
                    GROUP BY taxonomynode.node_id
                           """, (tuple(node_ids), dataset.id)
            )
            node_n_annotations_n_sounds = cursor.fetchall()

        annotation_numbers = {}
        for node_id, num_ann, num_sounds in node_n_annotations_n_sounds:
            # In commit https://github.com/MTG/freesound-datasets/commit/0a748ec3e8481cc1ca4625bced24e0aee9d059d0 we
            # introduced a single SQL query that go num_ann, num_sounds and num_missing_votes in one go.
            # However when tested in production we saw the query took hours to complete with full a sized dataset.
            # To make it work in a reasonable amount of time we now do a query to get nun validated annotations
            # for each node in the taxonomy. This should be refactored and use a single query to get all non
            # validated annotation counts for all nodes.
            num_missing_votes = dataset.num_non_validated_annotations_per_taxonomy_node(node_id)
            votes_stats = {
                'num_present_and_predominant': dataset.num_votes_with_value(node_id, 1.0),
                'num_present_not_predominant': dataset.num_votes_with_value(node_id, 0.5),
                'num_not_present': dataset.num_votes_with_value(node_id, -1.0),
                'num_unsure': dataset.num_votes_with_value(node_id, 0.0)
            }

            annotation_numbers[node_id] = {'num_annotations': num_ann,
                                           'num_sounds': num_sounds,
                                           'num_missing_votes': num_missing_votes,
                                           'votes_stats': votes_stats}

        nodes_data = []
        for node in dataset.taxonomy.get_all_nodes():
            try:
                counts = annotation_numbers[node.node_id]
            except KeyError:
                # Can happen if there are no annotations/sounds per a category
                counts = {
                    'num_sounds': 0,
                    'num_annotations': 0,
                    'num_missing_votes': 0,
                    'votes_stats': None,
                }
            node_stats = calculate_taxonomy_node_stats(dataset, node.as_dict(),
                                                       counts['num_sounds'],
                                                       counts['num_annotations'],
                                                       counts['num_missing_votes'],
                                                       counts['votes_stats'])
            node_stats.update({
                'id': node.node_id,
                'name': node.name,
            })
            nodes_data.append(node_stats)

        store.set(store_key, {
            'nodes_data': nodes_data,
        })
        logger.info('Finished computing data for {0}'.format(store_key))
    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_annotators_ranking(store_key, dataset_id, N=15):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        reference_date = datetime.datetime.today() - datetime.timedelta(days=7)
        ranking = list()
        ranking_last_week = list()
        for user in User.objects.all():
            n_annotations = Annotation.objects.filter(created_by=user, sound_dataset__dataset=dataset).count()
            n_votes = Vote.objects.filter(created_by=user, annotation__sound_dataset__dataset=dataset).count()
            ranking.append(
                (user.username, n_annotations + n_votes)
            )
            n_annotations_last_week = Annotation.objects.filter(
                created_at__gt=reference_date, created_by=user, sound_dataset__dataset=dataset).count()
            n_votes_last_week = Vote.objects.filter(
                created_at__gt=reference_date, created_by=user, annotation__sound_dataset__dataset=dataset).count()
            ranking_last_week.append(
                (user.username, n_annotations_last_week + n_votes_last_week)
            )

        ranking = sorted(ranking, key=lambda x: x[1], reverse=True)  # Sort by number of annotations
        ranking_last_week = sorted(ranking_last_week, key=lambda x: x[1], reverse=True)  # Sort by number of annotations

        store.set(store_key, {'ranking': ranking[:N], 'ranking_last_week': ranking_last_week[:N]})
        logger.info('Finished computing data for {0}'.format(store_key))
    except Dataset.DoesNotExist:
        pass
    except User.DoesNotExist:
        pass


@shared_task
def compute_gt_taxonomy_node():
    logger.info('Start computing number of ground truth annotation')
    dataset = Dataset.objects.get(short_name='fsd')
    taxonomy = dataset.taxonomy
    for node_id in taxonomy.get_all_node_ids():
        taxonomy_node = taxonomy.get_element_at_id(node_id)
        taxonomy_node.nb_ground_truth = taxonomy_node.annotation_set.filter(ground_truth__in=(0.5, 1)).count()
        taxonomy_node.save()
    logger.info('Finished computing number of ground truth annotation')


@shared_task
def refresh_sound_deleted_state():
    logger.info('Start refreshing freesound sound deleted state')
    sound_ids = Sound.objects.all().values_list('freesound_id', flat=True)
    results = query_freesound_by_id(sound_ids)
    deleted_sound_ids = set(sound_ids) - set([s.id for s in results])
    with transaction.atomic():
        for fs_sound_id in deleted_sound_ids:
            sound = Sound.objects.get(freesound_id=fs_sound_id)
            sound.deleted_in_freesound = True
            sound.save()
    logger.info('Finished refreshing freesound sound deleted state')
