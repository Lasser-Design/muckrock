"""
URL mappings for the Agency application
"""

from django.conf.urls.defaults import patterns, url

from agency import views
from muckrock.views import jurisdiction

agency_url = r'(?P<jurisdiction>[\w\d_-]+)-(?P<jidx>\d+)/(?P<slug>[\w\d_-]+)-(?P<idx>\d+)'
old_agency_url = r'(?P<jurisdiction>[\w\d_-]+)/(?P<slug>[\w\d_-]+)/(?P<idx>\d+)'

urlpatterns = patterns('',
    url(r'^$',                        views.list_, name='agency-list'),
    url(r'^%s/$' % agency_url,        views.detail, name='agency-detail'),
    url(r'^%s/update/$' % agency_url, views.update, name='agency-update'),
    url(r'^%s/flag/$' % agency_url,   views.flag, name='agency-flag'),
    url(r'^(?P<jurisdiction>[\w\d_-]+)-(?P<idx>\d+)/$',
                                      jurisdiction, name='agency-jurisdiction'),
    url(r'^(?P<action>\w+)/%s/$' % old_agency_url,
                                      views.redirect_old), 

)
