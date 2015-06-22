"""
URL routes for the project application
"""

from django.conf.urls import patterns, url

from muckrock.project import views

urlpatterns = patterns('',
    url(r'^create/$',
        views.ProjectCreateView.as_view(),
        name='project-create'),
    url(r'^(?P<slug>[\w-]+)/$',
        views.ProjectDetailView.as_view(),
        name='project-detail'),
    url(r'^(?P<slug>[\w-]+)/update/$',
        views.ProjectUpdateView.as_view(),
        name='project-update'),
    url(r'^(?P<slug>[\w-]+)/delete/$',
        views.ProjectDeleteView.as_view(),
        name='project-delete')
)
