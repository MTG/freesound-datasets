from contextlib import closing
from urllib.request import urlopen
from urllib.parse import urlencode
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from datasets.models import Dataset
from django.conf import settings


def get_access_token(request):
    code = request.GET.get('code')
    data = {
            'code': code,
            'client_id': settings.APP_CLIENT_ID,
            'client_secret': settings.APP_CLIENT_SECRET,
            'grant_type': 'authorization_code'
    }
    access_token_url = "https://test.freesound.org/apiv2/oauth2/access_token/"
    data = urlencode(data).encode('ascii')

    response = None
    with urlopen(access_token_url, data) as response:
        response = response.read().decode()
    return HttpResponse(response)


def dataset(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'dataset.html', {'dataset': dataset})


def download(request, short_name):
    dataset = get_object_or_404(Dataset, short_name=short_name)
    return render(request, 'download.html', {'dataset': dataset})
