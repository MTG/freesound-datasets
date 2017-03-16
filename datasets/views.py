import os
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404
from datasets.models import Dataset
from django.conf import settings
from datasets import utils


def get_access_token(request):
    code = request.GET.get('code', None)
    if not code:
        return HttpResponseBadRequest()

    data = {
            'code': code,
            'client_id': settings.FS_CLIENT_ID,
            'client_secret': settings.FS_CLIENT_SECRET,
            'grant_type': 'authorization_code'
    }
    access_token_url = "https://www.freesound.org/apiv2/oauth2/access_token/"
    data = urlencode(data).encode('ascii')

    try:
        with urlopen(access_token_url, data) as response:
            response = response.read().decode()
        return HttpResponse(response)
    except HTTPError:
        return HttpResponseBadRequest()

def download_script(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="fs_download_script.py"'
    script = utils.generate_download_script(dataset)
    response.write(script)
    return response

def dataset(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'dataset.html', {'dataset': dataset})


def dataset_taxonomy_table(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)

   # TODO: do the following query in django orm instead of a raw query
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
    return render(request, 'dataset_taxonomy_table.html', {
        'dataset': dataset,
        'node_n_annotations_n_sounds': node_n_annotations_n_sounds})


def download(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    script = utils.generate_download_script(dataset)
    return render(request, 'download.html', {'dataset': dataset, 'script': script})


def contribute(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'contribute.html', {'dataset': dataset})


def taxonomy_node(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    return render(request, 'taxonomy_node.html', {'dataset': dataset, 'node': node})
