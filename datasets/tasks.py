from datasets.models import Dataset, DatasetRelease, CandidateAnnotation, Vote, TaxonomyNode, Sound
from django.db.models import Count, Q
from django.contrib.auth.models import User
from django.db import transaction
from celery import shared_task
import pytz
from django.utils import timezone
from urllib.parse import quote
from utils.redis_store import store
from datasets.templatetags.dataset_templatetags import calculate_taxonomy_node_stats
from datasets.utils import query_freesound_by_id, chunks
import sys
import json
import math
import logging
import datetime
from collections import defaultdict
from datasets.utils import stem
logger = logging.getLogger('tasks')


@shared_task
def generate_release_index(dataset_id, release_id, max_sounds=None):
    """Deprecated. TODO: probably remove
    This function is not used. We use a management command to load releases.
    
    """
    dataset = Dataset.objects.get(id=dataset_id)
    dataset_release = DatasetRelease.objects.get(id=release_id)

    ground_truth_annotations = dataset.ground_truth_annotations
    dataset_release.ground_truth_annotations.add(*ground_truth_annotations)

    sounds_info = defaultdict(list)
    for result in ground_truth_annotations.values_list('sound_dataset__sound__freesound_id', 'taxonomy_node__node_id'):
        sounds_info[result[0]].append(result[1])

    # Calculate stats
    num_sounds = len(sounds_info)
    num_taxonomy_nodes = len(set([j for i in list(sounds_info.values()) for j in i]))
    num_annotations = ground_truth_annotations.count()

    # Make data structure
    release_data = {
        'meta': {
            'dataset': dataset.name,
            'release': dataset_release.release_tag,
            'num_sounds': num_sounds,
            'num_taxonomy_nodes': num_taxonomy_nodes,
            'num_annotations': num_annotations,
        },
        'sounds_info': list(sounds_info.items())
    }

    # Calculate taxonomy stats (num sounds per taxonomy node). We could avoid a db query here by counting in python
    taxonomy_node_stats = TaxonomyNode.objects.filter(ground_truth_annotations__dataset_release=dataset_release)\
        .annotate(num_sounds=Count('ground_truth_annotations',
                                   filter=Q(ground_truth_annotations__dataset_release=dataset_release)))\
        .values('name', 'num_sounds', 'node_id')
    for node in taxonomy_node_stats:
        node['url_id'] = quote(node['node_id'], safe='')

    dataset_release.release_data = release_data
    dataset_release.taxonomy_node_stats = list(taxonomy_node_stats)
    dataset_release.num_annotations = num_annotations
    dataset_release.num_sounds = num_sounds
    dataset_release.num_nodes = num_taxonomy_nodes
    dataset_release.processing_progress = 100  # REMOVE
    dataset_release.processing_last_updated = timezone.now()
    dataset_release.is_processed = True  # REMOVE
    dataset_release.save()


@shared_task
def compute_dataset_basic_stats(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        store.set(store_key, {
            'num_taxonomy_nodes': dataset.taxonomy.get_num_nodes(),
            'num_sounds': dataset.num_sounds_with_candidate,
            'num_annotations': dataset.num_annotations,
            'avg_annotations_per_sound': dataset.avg_annotations_per_sound,
            'percentage_validated_annotations': dataset.percentage_validated_annotations,
            'num_ground_truth_annotations': dataset.num_ground_truth_annotations,
            'num_verified_annotations': dataset.num_verified_annotations,
            'num_user_contributions': dataset.num_user_contributions,
            'percentage_verified_annotations': dataset.percentage_verified_annotations,
            'num_categories_reached_goal': dataset.num_categories_reached_goal,
            'num_non_omitted_nodes': dataset.num_non_omitted_nodes
        })
        logger.info('Finished computing data for {0}'.format(store_key))
    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_taxonomy_tree(store_key, dataset_id):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        taxonomy_tree = dataset.taxonomy.get_taxonomy_as_tree()
        store.set(store_key, taxonomy_tree)
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
                           , COUNT(candidateannotation.id)
                           , COUNT(DISTINCT(sound.id))
                        FROM datasets_candidateannotation candidateannotation
                  INNER JOIN datasets_sounddataset sounddataset
                          ON candidateannotation.sound_dataset_id = sounddataset.id
                  INNER JOIN datasets_sound sound
                          ON sound.id = sounddataset.sound_id
                  INNER JOIN datasets_taxonomynode taxonomynode
                          ON taxonomynode.id = candidateannotation.taxonomy_node_id
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
def compute_annotators_ranking(store_key, dataset_id, N=10):
    logger.info('Start computing data for {0}'.format(store_key))
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        reference_date = timezone.now() - datetime.timedelta(days=7)
        current_day_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ranking = list()
        ranking_last_week = list()
        ranking_today = list()
        ranking_agreement_today = list()
        for user in User.objects.all():
            # all time
            n_annotations = CandidateAnnotation.objects.filter(created_by=user, sound_dataset__dataset=dataset, type='MA').count()
            n_votes = Vote.objects.filter(created_by=user, candidate_annotation__sound_dataset__dataset=dataset).count()
            ranking.append(
                (user.username, n_annotations + n_votes)
            )

            # last week
            n_annotations_last_week = CandidateAnnotation.objects.filter(
                created_at__gt=reference_date, created_by=user, sound_dataset__dataset=dataset, type='MA').count()
            n_votes_last_week = Vote.objects.filter(
                created_at__gt=reference_date, created_by=user, candidate_annotation__sound_dataset__dataset=dataset).count()
            ranking_last_week.append(
                (user.username, n_annotations_last_week + n_votes_last_week)
            )

            # today
            agreement_score = 0
            n_annotations_today = CandidateAnnotation.objects.filter(
                created_at__gt=current_day_date, created_by=user, sound_dataset__dataset=dataset, type='MA').count()
            n_votes_today = Vote.objects.filter(
                created_at__gt=current_day_date, created_by=user, candidate_annotation__sound_dataset__dataset=dataset).count()

            ranking_today.append(
                (user.username, n_annotations_today + n_votes_today)
            )

            # agreement score today
            votes = Vote.objects.filter(created_by=user,
                                        candidate_annotation__sound_dataset__dataset=dataset,
                                        created_at__gt=current_day_date)
            for vote in votes:
                all_vote_values = [v.vote for v in vote.candidate_annotation.votes.all()]
                if all_vote_values.count(vote.vote) > 1:
                    agreement_score += 1
                elif len(all_vote_values) > 1:
                    pass
                else:
                    agreement_score += 0.5
            try:
                ranking_agreement_today.append(
                    (user.username, agreement_score/float(n_votes_today))
                )
            except ZeroDivisionError:
                ranking_agreement_today.append(
                    (user.username, 0)
                )

        ranking = sorted(ranking, key=lambda x: x[1], reverse=True)  # Sort by number of annotations
        ranking_last_week = sorted(ranking_last_week, key=lambda x: x[1], reverse=True)
        ranking_today = sorted(ranking_today, key=lambda x: x[1], reverse=True)
        ranking_agreement_today = sorted(ranking_agreement_today, key=lambda x: x[1], reverse=True)

        store.set(store_key, {'ranking': ranking[:N], 'ranking_last_week': ranking_last_week[:N],
                              'ranking_today': ranking_today, 'ranking_agreement_today': ranking_agreement_today})
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
        taxonomy_node.nb_ground_truth = taxonomy_node.num_ground_truth_annotations
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


@shared_task
def refresh_sound_extra_data():
    logger.info('Start refreshing freesound sound extra data')
    sound_ids = Sound.objects.all().values_list('freesound_id', flat=True)
    results = query_freesound_by_id(sound_ids, fields="id,name,analysis,images", descriptors="lowlevel.average_loudness")
    with transaction.atomic():
        for freesound_sound in results:
            sound = Sound.objects.get(freesound_id=freesound_sound.id)
            sound.extra_data.update(freesound_sound.as_dict())
            sound.save()
    logger.info('Finished refreshing freesound sound extra data')


@shared_task
def compute_priority_score_candidate_annotations():
    logger.info('Start computing priority score of candidate annotations')
    dataset = Dataset.objects.get(short_name='fsd')
    candidate_annotations = dataset.candidate_annotations.filter(ground_truth=None)\
                                   .select_related('sound_dataset__sound')\
                                   .annotate(num_present_votes=Count('votes',
                                                                     filter=~Q(votes__test='FA')
                                                                            & Q(votes__vote__in=('1', '0.5'))))
    num_annotations = candidate_annotations.count()
    count = 0
    # Iterate all the sounds in chunks so we can do all transactions of a chunk atomically
    for chunk in chunks(list(candidate_annotations), 500):
        sys.stdout.write('\rUpdating priority score of candidate annotation %i of %i (%.2f%%)'
                         % (count + 1, num_annotations, 100.0 * (count + 1) / num_annotations))
        sys.stdout.flush()
        with transaction.atomic():
            for candidate_annotation in chunk:
                count += 1
                candidate_annotation.priority_score = candidate_annotation.return_priority_score()
                candidate_annotation.save(update_fields=['priority_score'])
    logger.info('Finished computing priority score of candidate annotations')


@shared_task
def stem_dataset_sound_tags():
    logger.info('Start computing stem tags for FSD sounds')
    dataset = Dataset.objects.get(short_name='fsd')
    with transaction.atomic():
        for sound in dataset.sounds.all():
            tags = sound.extra_data['tags']
            stemmed_tags = [stem(tag) for tag in tags]
            sound.extra_data['stemmed_tags'] = stemmed_tags
            sound.save()
    logger.info('Finished computing stem tags for FSD sounds')
