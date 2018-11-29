from django.urls import include, re_path
from monitor.views import *


urlpatterns = [
    re_path(r'^(?P<short_name>[^\/]+)/monitor/$', monitor, name='monitor'),
    re_path(r'^(?P<short_name>[^\/]+)/monitor_category/(?P<node_id>[^\/]+)/$', monitor_category, name='monitor-category'),
    re_path(r'^(?P<short_name>[^\/]+)/monitor_user/(?P<user_id>[^\/]+)/$', monitor_user, name='monitor-user'),
    re_path(r'^(?P<short_name>[^\/]+)/mapping_category/(?P<node_id>[^\/]+)/$', mapping_category, name='mapping-category'),
    re_path(r'^(?P<short_name>[^\/]+)/sound_player/(?P<freesound_id>[^\/]+)/$', player, name='sound-player')
]
