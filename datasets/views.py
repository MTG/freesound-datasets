from django.shortcuts import render, get_object_or_404
from datasets.models import Dataset
from datasets.forms import JsonForm
from urllib.parse import unquote


def upload_taxonomy(request):
    if request.method == 'POST':
        form = JsonForm(request.POST, request.FILES)
        if form.is_valid():
            data = form.cleaned_data['json_file']
            taxonomy = models.Taxonomy.objects.create(data=data)
    else:
        form = JsonForm()
    return render(request, 'dataset/new_taxonomy.html', {'form': form,})


def dataset(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'dataset.html', {'dataset': dataset})


def download(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'download.html', {'dataset': dataset})


def explore_node(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    return render(request, 'explore_node.html', {'dataset': dataset, 'node': node})
