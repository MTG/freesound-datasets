from django.conf.urls import url, include
from monitor.views import *


urlpatterns = [
    url(r'^(?P<short_name>[^\/]+)/monitor/$', monitor, name='monitor'),
    url(r'^(?P<short_name>[^\/]+)/monitor_category/(?P<node_id>[^\/]+)/$', monitor_category, name='monitor-category'),
    url(r'^(?P<short_name>[^\/]+)/monitor_user/(?P<user_id>[^\/]+)/$', monitor_user, name='monitor-user'),
]
