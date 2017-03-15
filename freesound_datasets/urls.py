from django.conf.urls import url
from django.conf import settings
from django.contrib import admin
from freesound_datasets.views import index, crash_me
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from datasets.views import *
from datasets.models import Taxonomy


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^crash/$', crash_me, name='crash_me'),
    url(r'^admin/', admin.site.urls),
    url(r'new-taxonomy/$', upload_taxonomy, name='upload-taxonomy'),
    url(r'^(?P<short_name>[^\/]+)/$', dataset, name='dataset'),
    url(r'^(?P<short_name>[^\/]+)/download/$', download, name='download'),
    url(r'^(?P<short_name>[^\/]+)/taxonomy_table/$', dataset_taxonomy_table, name='taxonomy-table'),
    url(r'^(?P<short_name>[^\/]+)/explore/(?P<node_id>[^\/]+)/$', taxonomy_node, name='taxonomy-node'),
]

if settings.DEBUG:
    # We need to explicitly add staticfiles urls because we don't use runserver
    # https://docs.djangoproject.com/en/1.10/ref/contrib/staticfiles/#django.contrib.staticfiles.urls.staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
