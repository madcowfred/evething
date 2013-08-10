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

from decimal import Decimal

from django.db import models
from django.db.models import Sum

from thing.models.itemgroup import ItemGroup
from thing.models.marketgroup import MarketGroup

# ------------------------------------------------------------------------------

class Item(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=128)

    item_group = models.ForeignKey(ItemGroup)
    market_group = models.ForeignKey(MarketGroup, blank=True, null=True)

    portion_size = models.IntegerField()
    # 0.0025 -> 10,000,000,000
    volume = models.DecimalField(max_digits=16, decimal_places=4, default=0)

    base_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sell_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    buy_price = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return self.name

    def get_volume(self, days=7):
        iph_days = self.pricehistory_set.all()[:days]
        agg = self.pricehistory_set.filter(pk__in=iph_days).aggregate(Sum('movement'))
        if agg['movement__sum'] is None:
            return Decimal('0')
        else:
            return Decimal(str(agg['movement__sum']))

# ------------------------------------------------------------------------------
