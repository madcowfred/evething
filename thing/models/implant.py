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

from thing.models.item import Item


class Implant(models.Model):
    CHARISMA_ATTRIBUTE = 175
    INTELLIGENCE_ATTRIBUTE = 176
    MEMORY_ATTRIBUTE = 177
    PERCEPTION_ATTRIBUTE = 178
    WILLPOWER_ATTRIBUTE = 179
    IMPLANT_SLOT_ATTRIBUTE = 331

    item = models.OneToOneField(Item, primary_key=True)

    description = models.TextField()

    charisma_modifier = models.SmallIntegerField()
    intelligence_modifier = models.SmallIntegerField()
    memory_modifier = models.SmallIntegerField()
    perception_modifier = models.SmallIntegerField()
    willpower_modifier = models.SmallIntegerField()

    implant_slot = models.SmallIntegerField()

    class Meta:
        app_label = 'thing'

    def __unicode__(self):
        return "%s (Slot %d)" % (self.item.name, self.implant_slot)
