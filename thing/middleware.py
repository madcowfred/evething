import datetime

class LastSeenMiddleware(object):
    def process_request(self, request):
        if not request.user.is_authenticated():
            return None  
        profile = request.user.get_profile()
        profile.last_seen = datetime.datetime.now()
        profile.save()
        return None
