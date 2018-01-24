import os
from urllib.parse import urljoin
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
import datasets.freesound as fs


def generate_download_script(dataset):
    access_token_url = urljoin(settings.BASE_URL, reverse('get_access_token'))
    dataset_url = urljoin(settings.BASE_URL, reverse('dataset-sounds',
        kwargs={"short_name": dataset.short_name}))

    tvars = {
        'access_token_url': access_token_url,
        'dataset_url': dataset_url,
        'get_code_url': settings.FS_CLIENT_ID
    }
    return render_to_string('datasets/download_script.py', tvars)


def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]


def query_freesound_by_id(list_ids, fields="id,name", descriptors=""):
    """ Query Freesound by chunk of 50 sounds
        Retrieves only id of sounds """
    client = fs.FreesoundClient()
    client.set_token(settings.FS_CLIENT_SECRET)
    results = []
    for sub_list_ids in chunks(list_ids, 50):
        filter_str = 'id:(' + ' OR '.join([str(i) for i in sub_list_ids]) + ')'
        page_result = client.text_search(query="", fields=fields, page_size=50, filter=filter_str,
                                         descriptors=descriptors)
        results += [s for s in page_result]
    return results
