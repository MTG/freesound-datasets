from django.shortcuts import render, get_object_or_404
from datasets.models import Dataset
from monitor.tasks import compute_dataset_top_contributed_categories, compute_dataset_bad_mapping
from utils.async_tasks import data_from_async_task
from utils.redis_store import DATASET_TOP_CONTRIBUTED_CATEGORIES, DATASET_BAD_MAPPING_CATEGORIES


# Create your views here.
def monitor_categories(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    top_contributed_categories = data_from_async_task(compute_dataset_top_contributed_categories, [dataset.id], {},
                                                      DATASET_TOP_CONTRIBUTED_CATEGORIES.format(dataset.id), 60)

    bad_mapping_categories = data_from_async_task(compute_dataset_bad_mapping, [dataset.id], {},
                                                  DATASET_BAD_MAPPING_CATEGORIES.format(dataset.id), 60)

    return render(request, 'monitor/monitor_categories.html', {'dataset': dataset,
                                                               'top_contributed': top_contributed_categories,
                                                               'bad_mapping': bad_mapping_categories})
