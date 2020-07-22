import sys
import json
from django.core.management.base import BaseCommand
from datasets.models import *
from collections import defaultdict


class Command(BaseCommand):
    help = 'Create release for FSD. Use it as python manage.py load_dataset_release <release_tag> <annotation file>'

    def add_arguments(self, parser):
        parser.add_argument('release_tag', type=str)
        parser.add_argument('input_file', type=str)

    def handle(self, *args, **options):
        release_tag = options['release_tag']
        input_file = options['input_file']

        dataset = Dataset.objects.get(short_name='fsd')
        dataset_release = DatasetRelease.objects.create(
            release_tag=release_tag,
            dataset=dataset,
        )

        ground_truth_in_file = json.load(open(
            os.path.join(settings.DATASET_RELEASE_FILES_FOLDER, input_file), 'r'
        ))

        ground_truth_annotation_ids = []
        num_existing_gt = 0
        num_created_gt = 0

        print('\nProcessing annotations...\n')
        for idx, (node_id, fs_id, partition) in enumerate(ground_truth_in_file):
            try:
                gt = GroundTruthAnnotation.objects.get(taxonomy_node__node_id=node_id, sound_dataset__sound__freesound_id=fs_id)
                gt.partition = partition
                gt.save()
                num_existing_gt += 1
            except ObjectDoesNotExist:
                taxonomy_node = TaxonomyNode.objects.get(node_id=node_id)
                sound_dataset = SoundDataset.objects.get(sound__freesound_id=fs_id)
                gt = GroundTruthAnnotation.objects.create(
                    taxonomy_node=taxonomy_node,
                    sound_dataset=sound_dataset,
                    partition=partition,
                )
                num_created_gt += 1
            sys.stdout.write('\r %i of %i' % (idx, len(ground_truth_in_file)))
            sys.stdout.flush()
            ground_truth_annotation_ids.append(gt.id)

        ground_truth_annotations = GroundTruthAnnotation.objects.filter(id__in=ground_truth_annotation_ids)
        dataset_release.ground_truth_annotations.add(*ground_truth_annotations)

        print('\nNumber of annotations: {} (existing: {}, created: {})\n'.format(
            len(ground_truth_annotation_ids),
            num_existing_gt,
            num_created_gt
        ))

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