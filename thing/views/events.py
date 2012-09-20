#from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, InvalidPage, PageNotAnInteger
#from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *

# ---------------------------------------------------------------------------
# Events
@login_required
def events(request):
    # Get profile
    profile = request.user.get_profile()

    # Get a QuerySet of events for this user
    events = Event.objects.filter(user=request.user)

    # Create a new paginator
    paginator = Paginator(events, profile.entries_per_page)
    
    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        events = paginator.page(page)
    except (EmptyPage, InvalidPage):
        events = paginator.page(paginator.num_pages)
    
    # Render template
    return render_to_response(
        'thing/events.html',
        {
            'events': events,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
