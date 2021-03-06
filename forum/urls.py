"""
URLConf for Django-Forum.

django-forum assumes that the forum application is living under
/forum/.

Usage in your base urls.py:
    (r'^forum/', include('forum.urls')),

"""

from django.conf.urls.defaults import *
from forum.models import Forum
from forum.views import MyForumListView, MyThreadListView
from forum.feeds import RssForumFeed, AtomForumFeed
from forum.sitemap import ForumSitemap, ThreadSitemap, PostSitemap
from django.views.generic import ListView

feed_dict = {
    'rss' : RssForumFeed,
    'atom': AtomForumFeed
}

sitemap_dict = {
    'forums': ForumSitemap,
    'threads': ThreadSitemap,
    'posts': PostSitemap,
}

urlpatterns = patterns('',
    url(r'^$', ListView.as_view(model=Forum), name='forum_index'),
    
    url(r'^(?P<url>(rss|atom).*)/$', 'django.contrib.syndication.views.Feed', {'feed_dict': feed_dict}),

    url(r'^thread/(?P<thread>[0-9]+)/$', MyThreadListView.as_view(), name='forum_view_thread'),
    url(r'^thread/(?P<thread>[0-9]+)/reply/$', 'forum.views.reply', name='forum_reply_thread'),
    url(r'^thread/(?P<thread>[0-9]+)/post/(?P<id>[0-9]+)/edit/$', 'forum.views.edit_post', name='forum_edit_post'),
    url(r'^thread/(?P<thread>[0-9]+)/post/(?P<id>[0-9]+)/delete/$', 'forum.views.delete_post', name='forum_delete_post'),

    url(r'^subscriptions/$', 'forum.views.updatesubs', name='forum_subscriptions'),

    url(r'^(?P<slug>[-\w]+)/$', MyForumListView.as_view(), name='forum_thread_list'),
    url(r'^(?P<forum>[-\w]+)/new/$', 'forum.views.newthread', name='forum_new_thread'),

    url(r'^([-\w/]+/)(?P<forum>[-\w]+)/new/$', 'forum.views.newthread'),
    url(r'^([-\w/]+/)(?P<slug>[-\w]+)/$', MyForumListView.as_view(), name='forum_subforum_thread_list'),

    (r'^sitemap.xml$', 'django.contrib.sitemaps.views.index', {'sitemaps': sitemap_dict}),
    (r'^sitemap-(?P<section>.+)\.xml$', 'django.contrib.sitemaps.views.sitemap', {'sitemaps': sitemap_dict}),
)
