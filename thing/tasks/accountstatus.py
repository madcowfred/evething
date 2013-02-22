import os
import sys

from .apitask import APITask

# ---------------------------------------------------------------------------

class AccountStatus(APITask):
    name = 'thing.account_status'

    def run(self, url, taskstate_id, apikey_id, zero):
        if self.init(taskstate_id, apikey_id) is False:
            return

        # Fetch the API data
        if self.fetch_api(url, {}) is False or self.root is None:
            self.failed()
            return

        # Update paid_until
        paidUntil = self.parse_api_date(self.root.findtext('result/paidUntil'))
        if paidUntil != self.apikey.paid_until:
            self.apikey.paid_until = paidUntil
            self.apikey.save()

        # Job completed
        self.completed()

# ---------------------------------------------------------------------------
