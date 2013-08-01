# ------------------------------------------------------------------------------
# Copyright (c) 2010-2013, EVEthing team
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#     Redistributions of source code must retain the above copyright notice, this
#       list of conditions and the following disclaimer.
#     Redistributions in binary form must reproduce the above copyright notice,
#       this list of conditions and the following disclaimer in the documentation
#       and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
# OF SUCH DAMAGE.
# ------------------------------------------------------------------------------

from django.contrib.auth.models import User
from django.db import models

from thing.models.character import Character
from thing.models.corpwallet import CorpWallet

# ------------------------------------------------------------------------------

class Campaign(models.Model):
    user = models.ForeignKey(User)

    title = models.CharField(max_length=32)
    slug = models.SlugField(max_length=32)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    corp_wallets = models.ManyToManyField(CorpWallet, blank=True, null=True)
    characters = models.ManyToManyField(Character, blank=True, null=True)

    class Meta:
        app_label = 'thing'
        ordering = ('title',)

    def __unicode__(self):
        return self.title

    def get_transactions_filter(self, transactions):
        return transactions.filter(
            models.Q(corp_wallet__in=self.corp_wallets.all())
            |
            (
                models.Q(corp_wallet=None)
                &
                models.Q(character__in=self.characters.all())
            ),
            date__range=(self.start_date, self.end_date),
        )

# ------------------------------------------------------------------------------
