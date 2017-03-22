from django.conf.urls import url, include
from django.contrib import admin
from django.contrib.auth.views import logout
from freesound_datasets.views import index, crash_me, login
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from datasets.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^crash/$', crash_me, name='crash_me'),
    url(r'^login/$', login, name='login'),
    url(r'^logout/$', logout, {'next_page': '/'}, name='logout'),
    url(r'^admin/', admin.site.urls),
    url(r'^social/', include('social_django.urls', namespace='social')),
    url(r'^get-access-token/$', get_access_token, name='get_access_token'),
    url(r'^(?P<short_name>[^\/]+)/$', dataset, name='dataset'),
    url(r'^(?P<short_name>[^\/]+)/download-script/$', download_script, name='download-script'),
    url(r'^(?P<short_name>[^\/]+)/dataset-sounds/$', dataset_sounds, name='dataset-sounds'),
    url(r'^(?P<short_name>[^\/]+)/release/$', make_release, name='make-release'),
    url(r'^(?P<short_name>[^\/]+)/check_release_progresses/$', check_release_progresses, name='check-release-progresses'),
    url(r'^(?P<short_name>[^\/]+)/release/(?P<release_tag>[^\/]+)/$', change_release_type, name='change-release-type'),
    url(r'^(?P<short_name>[^\/]+)/release/(?P<release_tag>[^\/]+)/download/$', download_release, name='download-release'),
    url(r'^(?P<short_name>[^\/]+)/release/(?P<release_tag>[^\/]+)/delete/$', delete_release, name='delete-release'),
    url(r'^(?P<short_name>[^\/]+)/contribute/$', contribute, name='contribute'),
    url(r'^(?P<short_name>[^\/]+)/taxonomy_table/$', dataset_taxonomy_table, name='taxonomy-table'),
    url(r'^(?P<short_name>[^\/]+)/releases_table/$', dataset_releases_table, name='releases-table'),
    url(r'^(?P<short_name>[^\/]+)/explore/(?P<node_id>[^\/]+)/$', taxonomy_node, name='taxonomy-node'),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r'^__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
    # We need to explicitly add staticfiles urls because we don't use runserver
    # https://docs.djangoproject.com/en/1.10/ref/contrib/staticfiles/#django.contrib.staticfiles.urls.staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()
