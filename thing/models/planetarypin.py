# ------------------------------------------------------------------------------
# Copyright (c) 2010-2014, EVEthing team
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

from datetime import timedelta, datetime

from django.db import models

from thing.models.planetarycolony import Colony
from thing.models.item import Item


class Pin(models.Model):
    """Planetary Pin"""
    pin_id = models.BigIntegerField(db_index=True)
    colony = models.ForeignKey(Colony)

    type = models.ForeignKey(Item, related_name='+')
    schematic = models.IntegerField()

    cycle_time = models.IntegerField()
    quantity_per_cycle = models.IntegerField()

    installed = models.DateTimeField()
    expires = models.DateTimeField()
    last_launched = models.DateTimeField()

    content_size = models.DecimalField(max_digits=16, decimal_places=4, default=0)

    class Meta:
        app_label = 'thing'

    def __str__(self):
        return '%s - %s' % (self.colony, self.type.name)

    EXTRACTORS = [2848, 3060, 3061, 3062, 3063, 3064, 3067, 3068]
    LAUNCHPADS = [2544, 2543, 2552, 2555, 2542, 2556, 2557, 2256]
    STORAGE = [2541, 2536, 2257, 2558, 2535, 2560, 2561, 2562] + LAUNCHPADS

    def get_capacity(self):
        if self.type_id in self.LAUNCHPADS:
            return 10000
        elif self.type_id in self.STORAGE:
            return 12000

        return 0

    def percent_full(self):
        cap = self.get_capacity()
        if cap > 0:
            return (self.content_size/cap)*100
        else:
            return 0

    def alert_class(self):
        diff = self.expires - datetime.now()
        if diff >= timedelta(days=1):
            return 'success'
        elif diff > timedelta(hours=8):
            return 'warning'
        else:
            return 'danger'


class PinContent(models.Model):
    pin = models.ForeignKey(Pin)
    item = models.ForeignKey(Item, related_name='+')
    quantity = models.IntegerField()

    class Meta:
        app_label = 'thing'
