from django.shortcuts import render, get_object_or_404
from urllib.parse import unquote
from datasets.models import Dataset
from monitor.tasks import compute_dataset_top_contributed_categories, compute_dataset_bad_mapping, \
    compute_dataset_difficult_agreement, compute_remaining_annotations_with_duration
from utils.async_tasks import data_from_async_task
from utils.redis_store import DATASET_TOP_CONTRIBUTED_CATEGORIES, DATASET_BAD_MAPPING_CATEGORIES, \
    DATASET_DIFFICULT_AGREEMENT_CATEGORIES, DATASET_REMAINING_CANDIDATE_ANNOTATIONS_PER_CATEGORIES


# Create your views here.
def monitor_categories(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    top_contributed_categories = data_from_async_task(compute_dataset_top_contributed_categories, [dataset.id], {},
                                                      DATASET_TOP_CONTRIBUTED_CATEGORIES.format(dataset.id), 60)

    bad_mapping_categories = data_from_async_task(compute_dataset_bad_mapping, [dataset.id], {},
                                                  DATASET_BAD_MAPPING_CATEGORIES.format(dataset.id), 60)

    difficult_agreement_categories = data_from_async_task(compute_dataset_difficult_agreement, [dataset.id], {},
                                                          DATASET_DIFFICULT_AGREEMENT_CATEGORIES.format(dataset.id), 60)

    remaining_annotations = data_from_async_task(compute_remaining_annotations_with_duration, [dataset.id], {},
                                                 DATASET_REMAINING_CANDIDATE_ANNOTATIONS_PER_CATEGORIES
                                                 .format(dataset.id), 60)

    return render(request, 'monitor/monitor_categories.html', {'dataset': dataset,
                                                               'top_contributed': top_contributed_categories,
                                                               'bad_mapping': bad_mapping_categories,
                                                               'difficult_agreement': difficult_agreement_categories,
                                                               'remaining_annotations': remaining_annotations})


def monitor_category(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    example_ids = node.freesound_examples.values_list('freesound_id', flat=True)
    verification_example_ids = node.freesound_examples_verification.values_list('freesound_id', flat=True)
    false_verification_example_ids = node.freesound_false_examples.values_list('freesound_id', flat=True)
    return render(request, 'monitor/monitor_category.html', {'dataset': dataset,
                                                             'node': node,
                                                             'example_ids': example_ids,
                                                             'verification_example_ids': verification_example_ids,
                                                             'false_verification_example_ids': false_verification_example_ids})
