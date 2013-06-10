"""
All forum logic is kept here - displaying lists of forums, threads 
and posts, adding new threads, and adding replies.
"""

from datetime import datetime
from django.shortcuts import get_object_or_404, render_to_response
from django.http import Http404, HttpResponse, HttpResponseRedirect, HttpResponseServerError, HttpResponseForbidden, HttpResponseNotAllowed
from django.template import RequestContext, Context, loader
from django import forms
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.defaultfilters import striptags, wordwrap
from django.contrib.sites.models import Site
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext as _
from django.views.generic.list import ListView
from django.contrib.auth.decorators import login_required

from forum.models import Forum,Thread,Post,Subscription
from forum.forms import CreateThreadForm, ReplyForm, EditPost

FORUM_PAGINATION = getattr(settings, 'FORUM_PAGINATION', 10)
LOGIN_URL = getattr(settings, 'LOGIN_URL', '/accounts/login/')


class MyForumListView(ListView):
    """
    Displays a list of threads within a forum.
    Threads are sorted by their sticky flag, followed by their
    most recent post.
    """
    template_name = 'forum/thread_list.html'
    context_object_name = 'thread'
    paginate_by = FORUM_PAGINATION

    def get_queryset(self):
        try:
            self.forum = Forum.objects.for_groups(self.request.user.groups.all()).select_related().get(slug=self.kwargs.get('slug'))
        except Forum.DoesNotExist:
            raise Http404
        self.form = CreateThreadForm(forum=self.forum)
        self.child_forums = self.forum.child.for_groups(self.request.user.groups.all())
	return Thread.objects.filter(forum__id=self.forum.id)

    def get_context_data(self, **kwargs):
        context = super(MyForumListView, self).get_context_data(**kwargs)
        context['forum'] =  self.forum,
        context['child_forums'] =  self.child_forums,
        context['form'] =  self.form
        return context

class MyThreadListView(ListView):
    """
    Increments the viewed count on a thread then displays the
    posts for that thread, in chronological order.
    """
    paginate_by = FORUM_PAGINATION
    context_object_name='post'
    template_name='forum/thread.html'

    def get_queryset(self):
        try:
            self.thread = Thread.objects.select_related().get(pk=self.kwargs.get('thread'))
            if not Forum.objects.has_access(self.thread.forum, self.request.user.groups.all()):
                raise Http404
        except Thread.DoesNotExist:
            raise Http404

        self.forum = ''
        self.subscription = None
        if self.request.user.is_authenticated():
            self.subscription = self.thread.subscription_set.select_related().filter(author=self.request.user)
        self.form = ''
        return self.thread.post_set.select_related('author').all().order_by('time')

    def get_object(self):
        object = super(MyThreadListView, self).get_object()
        object.views += 1
        object.save()
        return object

    def get_context_data(self, **kwargs):
        context = super(MyThreadListView, self).get_context_data(**kwargs)
        context['forum'] = self.forum
        context['thread'] = self.thread
        context['subscription'] = self.subscription
        context['form'] = self.form
        return context


@login_required
def reply(request, thread, extra_context=None):
    """
    If a thread isn't closed, and the user is logged in, post a reply
    to a thread. Note we don't have "nested" replies at this stage.
    """
    t = get_object_or_404(Thread, pk=thread)
    if t.closed:
        return HttpResponseServerError()
    if not Forum.objects.has_access(t.forum, request.user.groups.all()):
        return HttpResponseForbidden()

    preview = False
    p = None

    if request.method == "POST":
        form = ReplyForm(request.POST)
        preview = request.POST.get('preview')
        p = Post(
            thread=t, 
            author=request.user,
            time=datetime.now(),
            )
        if form.is_valid():
            p.body = form.cleaned_data['body']
            if not preview:
                p.save()

                sub = Subscription.objects.filter(thread=t, author=request.user)
                if form.cleaned_data.get('subscribe',False):
                    if not sub:
                        s = Subscription(
                            author=request.user,
                            thread=t
                            )
                        s.save()
                else:
                    if sub:
                        sub.delete()

            # this needs refactorings

            if not preview and t.subscription_set.count() > 0:
                # Subscriptions are updated now send mail to all the authors subscribed in
                # this thread.
                mail_subject = ''
                try:
                    mail_subject = settings.FORUM_MAIL_PREFIX 
                except AttributeError:
                    mail_subject = '[Forum]'

                mail_from = ''
                try:
                    mail_from = settings.FORUM_MAIL_FROM
                except AttributeError:
                    mail_from = settings.DEFAULT_FROM_EMAIL

                mail_tpl = loader.get_template('forum/notify.txt')
                c = Context({
                    'body': wordwrap(striptags(body), 72),
                    'site' : Site.objects.get_current(),
                    'thread': t,
                    })

                email = EmailMessage(
                        subject=mail_subject+' '+striptags(t.title),
                        body= mail_tpl.render(c),
                        from_email=mail_from,
                        bcc=[s.author.email for s in t.subscription_set.all()],)
                email.send(fail_silently=True)

            if not preview:
                return HttpResponseRedirect(p.get_absolute_url())
    else:
        form = ReplyForm()
    
    return render_to_response('forum/reply.html',
        RequestContext(request, {
            'form': form,
            'forum': t.forum,
            'post': p,
            'preview': preview,
            'thread': t,
        }))


@login_required
def newthread(request, forum, extra_context=None):
    """
    Rudimentary post function - this should probably use 
    newforms, although not sure how that goes when we're updating 
    two models.

    Only allows a user to post if they're logged in.
    """
    f = get_object_or_404(Forum, slug=forum)
    
    if not Forum.objects.has_access(f, request.user.groups.all()):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = CreateThreadForm(forum=f, data=request.POST)
        if form.is_valid():
            t = Thread(
                forum=f,
                title=form.cleaned_data['title'],
            )
            t.save()

            p = Post(
                thread=t,
                author=request.user,
                body=form.cleaned_data['body'],
                time=datetime.now(),
            )
            p.save()
    
            if form.cleaned_data.get('subscribe', False):
                s = Subscription(
                    author=request.user,
                    thread=t
                    )
                s.save()
            return HttpResponseRedirect(t.get_absolute_url())
    else:
        form = CreateThreadForm(forum=f)

    ctx = extra_context or {}
    ctx.update({'form': form,
        'forum': f,
        })

    return render_to_response('forum/newthread.html',
        ctx, RequestContext(request))

def updatesubs(request):
    """
    Allow users to update their subscriptions all in one shot.
    """
    if not request.user.is_authenticated():
        return HttpResponseRedirect('%s?next=%s' % (LOGIN_URL, request.path))

    subs = Subscription.objects.select_related().filter(author=request.user)

    if request.POST:
        # remove the subscriptions that haven't been checked.
        post_keys = [k for k in request.POST.keys()]
        for s in subs:
            if not str(s.thread.id) in post_keys:
                s.delete()
        return HttpResponseRedirect(reverse('forum_subscriptions'))

    return render_to_response('forum/updatesubs.html',
        RequestContext(request, {
            'subs': subs,
            'next': request.GET.get('next')
        }))
       
@login_required
def delete_post(request, id, thread, extra_context=None,
        template_name=None):
    post = get_object_or_404(Post, id=id, thread__id=thread)
    if not request.user == post.author:
        raise Http404
    if request.method == 'POST' and request.POST.get('confirm'):
        post.delete()
        request.user.message_set.create(message=_('Deleted post'))
        return HttpResponseRedirect(post.thread.get_absolute_url())

    ctx = extra_context or {}
    ctx['post'] = post

    return render_to_response(template_name or 'forum/post_delete.html',
            RequestContext(request, ctx))



@login_required
def edit_post(request, id, thread=None, form_class=None, 
        template_name=None, extra_context=None):
    """
    edit existing post view
    """

    post = get_object_or_404(Post, id=id, thread__id=thread)
    form_class = form_class or EditPost

    if not request.user == post.author:
        raise Http404

    preview = False

    if request.method == 'POST':
        preview = request.POST.get('preview', False)
        form = form_class(data=request.POST, instance=post)
        if form.is_valid():
            post = form.save(commit=not preview)
            if not preview:
                return HttpResponseRedirect(post.thread.get_absolute_url())
    else:
        form = form_class(instance=post)
    

    ctx = extra_context or {}
    ctx.update({'form': form,
        'post': post,
        'preview': preview,
        })

    return render_to_response(template_name or 'forum/post_edit.html',
        ctx, RequestContext(request))
