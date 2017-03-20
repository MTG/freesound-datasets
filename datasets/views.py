from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.cache import cache_page
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from datasets.models import Dataset
from django.conf import settings
from datasets import utils
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter


def get_access_token(request):
    code = request.GET.get('code', None)
    refresh_token = request.GET.get('refresh_token', None)
    if not code and not refresh_token:
        return HttpResponseBadRequest()

    data = {
            'client_id': settings.FS_CLIENT_ID,
            'client_secret': settings.FS_CLIENT_SECRET,
    }
    if code:
        data['code'] = code
        data['grant_type'] = 'authorization_code'
    else:
        data['refresh_token'] = refresh_token
        data['grant_type'] = 'refresh_token'

    access_token_url = "https://www.freesound.org/apiv2/oauth2/access_token/"
    data = urlencode(data).encode('ascii')

    try:
        with urlopen(access_token_url, data) as response:
            response = response.read().decode()
        return HttpResponse(response)
    except HTTPError:
        return HttpResponseBadRequest()


@cache_page(60 * 60 * 24)
def dataset_sounds(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return JsonResponse({'sounds': [s.id for s in dataset.sounds.all()]})


@login_required
@user_passes_test(lambda u: u.is_staff)  # Restrict download to admins (this is a temporal thing)
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


@login_required
def download(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    script = utils.generate_download_script(dataset)
    formatted_script = highlight(script, PythonLexer(), HtmlFormatter())
    highlighting_styles = HtmlFormatter().get_style_defs('.highlight')
    return render(request, 'download.html', {'dataset': dataset,
                                             'formatted_script': formatted_script,
                                             'highlighting_styles': highlighting_styles})


@login_required
def contribute(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'contribute.html', {'dataset': dataset})


def taxonomy_node(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    return render(request, 'taxonomy_node.html', {'dataset': dataset, 'node': node})
