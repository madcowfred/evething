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

from django.db import models

from thing.models.character import Character
from thing.models.inventoryflag import InventoryFlag
from thing.models.item import Item
from thing.models.station import Station
from thing.models.system import System


class Asset(models.Model):
    """Assets"""
    asset_id = models.BigIntegerField(db_index=True)
    parent = models.BigIntegerField(default=0)

    character = models.ForeignKey(Character)
    corporation_id = models.IntegerField(default=0, db_index=True)
    system = models.ForeignKey(System)
    station = models.ForeignKey(Station, blank=True, null=True)

    item = models.ForeignKey(Item)
    name = models.CharField(max_length=128, default='')
    inv_flag = models.ForeignKey(InventoryFlag)
    quantity = models.IntegerField()
    raw_quantity = models.IntegerField()
    singleton = models.BooleanField()

    class Meta:
        app_label = 'thing'

    def system_or_station(self):
        try:
            return self.station.name
        except:
            try:
                return self.system.name
            except:
                return None

    def is_blueprint(self):
        if self.item.item_group.category.name == 'Blueprint':
            return min(-1, self.raw_quantity)
        else:
            return 0

    def get_sell_price(self):
        blueprint = self.is_blueprint()

        if blueprint == 0:
            return self.item.sell_price
        # BPOs use the base (NPC) price
        elif blueprint == -1:
            return self.item.base_price
        # BPCs count as 0 value for now
        else:
            return 0
