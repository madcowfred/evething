from django.core.cache import cache

from .apitask import APITask

# ---------------------------------------------------------------------------

class ServerStatus(APITask):
    name = 'thing.server_status'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        if self.fetch_api(url, {}, use_auth=False) is False or self.root is None:
            return

        # Parse the API data
        serverOpen = (self.root.findtext('result/serverOpen', 'False') == 'True')
        onlinePlayers = int(self.root.findtext('result/onlinePlayers', '0'))

        # Cache the data
        cache.set('server_open', serverOpen, 300)
        cache.set('online_players', onlinePlayers, 300)

        return True

# ---------------------------------------------------------------------------
