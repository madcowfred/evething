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

# Inventory flags
FLAG_NICE = {
    'HiSlot': ('High Slot', 0),
    'MedSlot': ('Mid Slot', 1),
    'LoSlot': ('Low Slot', 2),
    'RigSlot': ('Rig Slot', 3),
    'DroneBay': ('Drone Bay', 4),
    'ShipHangar': ('Ship Hangar', 5),
    'SpecializedFuelBay': ('Fuel Bay', 6),
}


class InventoryFlag(models.Model):
    id = models.IntegerField(primary_key=True)
    name = models.CharField(max_length=64)
    text = models.CharField(max_length=128)

    class Meta:
        app_label = 'thing'

    def nice_name(self):
        for pre, data in FLAG_NICE.items():
            if self.name.startswith(pre):
                return data[0]

        return self.name

    def sort_order(self):
        for pre, data in FLAG_NICE.items():
            if self.name.startswith(pre):
                return data[1]

        return 999
