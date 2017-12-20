from django.shortcuts import render, get_object_or_404
from datasets.models import Dataset


# Create your views here.
def monitor_categories(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'monitor/monitor_categories.html', {'dataset': dataset})
