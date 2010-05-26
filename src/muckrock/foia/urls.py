"""
URL mappings for the FOIA application
"""

from django.conf.urls.defaults import patterns, url
from django.contrib.auth.decorators import login_required
from django.views.generic import list_detail

from foia import views
from foia.models import FOIARequest
from foia.feeds import LatestSubmittedRequests, LatestDoneRequests

foia_qs = {'queryset': FOIARequest.objects.all(),
           'paginate_by': 10}

urlpatterns = patterns('',
    url(r'^$',                              login_required(list_detail.object_list),
                                            foia_qs, name='foia-index'),
    url(r'^list/$',                         login_required(list_detail.object_list),
                                            foia_qs, name='foia-list'),
    url(r'^list/(?P<user_name>[\w\d_]+)/$', views.list_by_user, name='foia-list-user'),
    url(r'^list/(?P<sort_order>asc|desc)/(?P<field>[\w]+)/$',
                                        views.sorted_list, name='foia-sorted-list'),
    url(r'^new/$',                          views.create, name='foia-create'),
    url(r'^view/(?P<jurisdiction>[\w\d_-]+)/(?P<user_name>[\w\d_]+)/(?P<slug>[\w\d_-]+)/$',
                                        views.detail, name='foia-detail'),
    url(r'^view/(?P<jurisdiction>[\w\d_-]+)/(?P<user_name>[\w\d_]+)/(?P<slug>[\w\d_-]+)/'
         'doc/(?P<page>\d+)/$',
                                        views.document_detail, name='foia-doc-detail'),
    url(r'^update/(?P<user_name>[\w\d_]+)/(?P<slug>[\w\d_-]+)/$',
                                        views.update, name='foia-update'),
    url(r'^feeds/submitted/$',          LatestSubmittedRequests(), name='foia-submitted-feed'),
    url(r'^feeds/completed/$',          LatestDoneRequests(), name='foia-done-feed'),
)
