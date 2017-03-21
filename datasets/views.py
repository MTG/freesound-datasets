from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode, unquote
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.views.decorators.cache import cache_page
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.core.urlresolvers import reverse
from datasets.models import Dataset, DatasetRelease
from datasets import utils
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter
from django.db.models import Count
import json
import os


#######################
# EXPLORE DATASET VIEWS
#######################

def dataset(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    user_is_maintainer = dataset.user_is_maintainer(request.user)
    if user_is_maintainer:
        dataset_releases_for_user = dataset.releases
    else:
        dataset_releases_for_user = dataset.releases.filter(type="PU")  # Only get public ones
    return render(request, 'dataset.html', {
        'dataset': dataset,
        'user_is_maintainer': user_is_maintainer,
        'dataset_releases_for_user': dataset_releases_for_user
    })


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


def taxonomy_node(request, short_name, node_id):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    node_id = unquote(node_id)
    node = dataset.taxonomy.get_element_at_id(node_id)
    return render(request, 'taxonomy_node.html', {'dataset': dataset, 'node': node})


#############################
# CONTRIBUTE TO DATASET VIEWS
#############################

@login_required
def contribute(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'contribute.html', {'dataset': dataset})


########################
# DOWNLOAD DATASET VIEWS
########################

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


@login_required
def download_release(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    release = get_object_or_404(DatasetRelease, dataset=dataset, release_tag=release_tag)
    if release.type is not 'PU' and not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    script = utils.generate_download_script(dataset)
    formatted_script = highlight(script, PythonLexer(), HtmlFormatter())
    highlighting_styles = HtmlFormatter().get_style_defs('.highlight')
    return render(request, 'download.html', {'dataset': dataset,
                                             'release': release,
                                             'formatted_script': formatted_script,
                                             'highlighting_styles': highlighting_styles})


def __prepare_release_data(dataset, release_tag, release_type):
    # Get sounds' info and annotations
    sounds_info = list()
    N = 5
    n_sounds = 0
    n_annotations = 0
    n_validated_annotations = 0
    for sound in dataset.sounds.all()[:N]:
        annotations = sound.get_annotations(dataset)
        if annotations:
            sounds_info.append((
                sound.id, [item.value for item in annotations]
            ))
            n_sounds += 1
            n_annotations += annotations.count()
            n_validated_annotations += annotations.annotate(num_votes=Count('votes')).filter(num_votes__lt=0).count()

    # Make data structure
    release_data = {
       'meta': {
           'dataset': dataset.name,
           'release': release_tag,
           'num_sounds': n_sounds,
           'num_annotations': n_annotations,
           'num_validated_annotations': n_validated_annotations
       },
       'sounds_info': sounds_info,
    }
    return release_data


@login_required
def make_release(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    if request.method == 'POST':
        # TODO: use a model form
        release_tag = request.POST.get('release-tag')
        release_type = request.POST.get('release-type', None)
        if release_type not in [item[0] for item in DatasetRelease.TYPE_CHOICES]:
            release_type = DatasetRelease.TYPE_CHOICES[0][0]

        # Prepare release data
        # TODO: this operation can take a long time, so we should handle the making of a release in an
        # TODO: asychronous way (using celery?)
        release_data = __prepare_release_data(dataset, release_tag, release_type)

        # Create db entry object
        dataset_release = DatasetRelease.objects.create(
            dataset=dataset,
            num_sounds=release_data['meta']['num_sounds'],
            num_annotations=release_data['meta']['num_annotations'],
            num_validated_annotations=release_data['meta']['num_validated_annotations'],
            release_tag=release_tag,
            type=release_type,
        )

        # Save release data to file
        json.dump(release_data, open(dataset_release.index_file_path, 'w'))

    # Redirect to dataset main page
    return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))


@login_required
def change_release_type(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    release = get_object_or_404(DatasetRelease, dataset=dataset, release_tag=release_tag)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    release_type = request.GET.get('release-type', None)
    if release_type not in [item[0] for item in DatasetRelease.TYPE_CHOICES]:
        release_type = DatasetRelease.TYPE_CHOICES[0][0]
    release.type = release_type
    release.save()

    return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))


@login_required
def delete_release(request, short_name, release_tag):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    release = get_object_or_404(DatasetRelease, dataset=dataset, release_tag=release_tag)
    if not dataset.user_is_maintainer(request.user):
        raise HttpResponseNotAllowed

    # Remove related files and db object
    try:
        os.remove(release.index_file_path)
    except FileNotFoundError:
        pass
    release.delete()

    return HttpResponseRedirect(reverse('dataset', args=[dataset.short_name]))
