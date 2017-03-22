from datasets.models import Dataset, DatasetRelease, Annotation
from django.db.models import Count
from django.contrib.auth.models import User
from celery import shared_task
from django.utils import timezone
from utils.redis_store import store, DATASET_BASIC_STATS_KEY_TEMPLATE, DATASET_TAXONOMY_STATS_KEY_TEMPLATE, \
    DATASET_ANNOTATORS_RANKING_TEMPLATE
from datasets.templatetags.dataset_templatetags import taxonomy_node_stats
import json
import math


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
def compute_dataset_basic_stats(dataset_id):
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        store.set(DATASET_BASIC_STATS_KEY_TEMPLATE.format(dataset.id), {
            'num_taxonomy_nodes': dataset.taxonomy.get_num_nodes(),
            'num_sounds': dataset.num_sounds,
            'num_annotations': dataset.num_annotations,
            'avg_annotations_per_sound': dataset.avg_annotations_per_sound,
            'percentage_validated_annotations': dataset.percentage_validated_annotations
        })
    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_dataset_taxonomy_stats(dataset_id):
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        node_ids = dataset.taxonomy.get_all_node_ids()
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("""
                    SELECT "datasets_annotation"."value", COUNT("datasets_annotation"."id"), COUNT(DISTINCT("datasets_sound"."id"))
                    FROM "datasets_annotation"
                    INNER JOIN "datasets_sounddataset" ON ("datasets_annotation"."sound_dataset_id" = "datasets_sounddataset"."id")
                    INNER JOIN "datasets_sound" ON ("datasets_sound"."id" = "datasets_sounddataset"."sound_id")
                    WHERE ("datasets_annotation"."value" IN ({0}) AND "datasets_sounddataset"."dataset_id" = {1})
                    GROUP BY "datasets_annotation"."value";
                    """.format(
                str(node_ids)[1:-1],
                dataset.id
            ))
            node_n_annotations_n_sounds = cursor.fetchall()

        nodes_data = list()
        for node in dataset.taxonomy.get_all_nodes():
            node_stats = taxonomy_node_stats(dataset, node['id'], node_n_annotations_n_sounds)
            node_stats.update({
                'id': node['id'],
                'name': node['name'],
            })
            nodes_data.append(node_stats)

        store.set(DATASET_TAXONOMY_STATS_KEY_TEMPLATE.format(dataset.id), {
            'nodes_data': nodes_data,
        })
    except Dataset.DoesNotExist:
        pass


@shared_task
def compute_annotators_ranking(dataset_id, user_id, N=10):
    try:
        dataset = Dataset.objects.get(id=dataset_id)
        user = User.objects.get(id=user_id)

        ranking = list()
        for user in User.objects.all():
            ranking.append(
                (user.username, Annotation.objects.filter(created_by=user, sound_dataset__dataset=dataset).count())
            )
            ranking = sorted(ranking, key=lambda x: x[1])  # Sort by number of annotations

            store.set(DATASET_ANNOTATORS_RANKING_TEMPLATE.format(dataset.id), {
                'ranking': ranking[:N],
            })
    except Dataset.DoesNotExist:
        pass
    except User.DoesNotExist:
        pass