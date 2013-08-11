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

import re

from django.db import models

from thing.models.character import Character

# ------------------------------------------------------------------------------

TAG_RE = re.compile('<[^>]+>')

class MailMessage(models.Model):
    character = models.ForeignKey(Character)

    message_id = models.BigIntegerField()
    sender_id = models.IntegerField()
    sent_date = models.DateTimeField()
    title = models.CharField(max_length=255)
    to_characters = models.ManyToManyField(Character, related_name='+')
    to_corp_or_alliance_id = models.IntegerField()
    to_list_id = models.IntegerField()

    body = models.TextField(blank=True, null=True)

    read = models.BooleanField(default=False)

    class Meta:
        app_label = 'thing'
        ordering = ('-sent_date',)

    def stripped_body(self):
        return TAG_RE.sub('', self.body)

# ------------------------------------------------------------------------------
