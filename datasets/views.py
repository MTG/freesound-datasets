from django.shortcuts import render, get_object_or_404
from datasets.models import Dataset


def dataset(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'dataset.html', {'dataset': dataset})


def download(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'download.html', {'dataset': dataset})
