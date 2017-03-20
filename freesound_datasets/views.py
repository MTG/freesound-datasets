from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.conf import settings
from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from datasets.models import Dataset


@login_required
@user_passes_test(lambda u: u.is_staff, login_url='/')
def crash_me(request):
    raise Exception('Everything is under control')


def index(request):
    default_dataset = get_object_or_404(Dataset, name=settings.DEFAULT_DATASET_NAME)
    return HttpResponseRedirect(reverse('dataset', args=[default_dataset.short_name]))


def login(request):
    next = request.GET.get('next', '')
    return render(request, 'login.html', {'next': next})
