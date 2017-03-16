import os
from urllib.parse import urljoin
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string

def generate_download_script(dataset):
    access_token_url = urljoin(settings.BASE_URL, reverse('get_access_token'))
    dataset_url = urljoin(settings.BASE_URL, reverse('dataset-sounds',
        kwargs={"short_name": dataset.short_name}))

    tvars = {
        'access_token_url': access_token_url,
        'dataset_url': dataset_url,
        'get_code_url': settings.FS_CLIENT_ID
    }
    return render_to_string('download_script.py', tvars)
