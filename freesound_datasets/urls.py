from django.conf.urls import url
from django.contrib import admin
from freesound_datasets.views import index, crash_me
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from datasets.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^crash/$', crash_me, name='crash_me'),
    url(r'^admin/', admin.site.urls),
    url(r'^get-access-token/$', get_access_token, name='get_access_token'),
    url(r'^download-script/(?P<short_name>[^\/]+)/$', download_script, name='download-script'),
    url(r'^(?P<short_name>[^\/]+)/$', dataset, name='dataset'),
    url(r'^(?P<short_name>[^\/]+)/download/$', download, name='download'),
    url(r'^(?P<short_name>[^\/]+)/contribute/$', contribute, name='contribute'),
    url(r'^(?P<short_name>[^\/]+)/taxonomy_table/$', dataset_taxonomy_table, name='taxonomy-table'),
    url(r'^(?P<short_name>[^\/]+)/explore/(?P<node_id>[^\/]+)/$', taxonomy_node, name='taxonomy-node'),
]

if settings.DEBUG:
    # We need to explicitly add staticfiles urls because we don't use runserver
    # https://docs.djangoproject.com/en/1.10/ref/contrib/staticfiles/#django.contrib.staticfiles.urls.staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
