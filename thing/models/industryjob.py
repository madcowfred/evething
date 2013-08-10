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
from thing.models.corporation import Corporation
from thing.models.inventoryflag import InventoryFlag
from thing.models.item import Item
from thing.models.system import System

# ------------------------------------------------------------------------------
# Industry jobs
class IndustryJob(models.Model):
    FAILED_STATUS = 0
    DELIVERED_STATUS = 1
    ABORTED_STATUS = 2
    GM_ABORTED_STATUS = 3
    INFLIGHT_UNANCHORED_STATUS = 4
    DESTROYED_STATUS = 5
    STATUS_CHOICES = (
        (FAILED_STATUS, 'Failed'),
        (DELIVERED_STATUS, 'Delivered'),
        (ABORTED_STATUS, 'Aborted'),
        (GM_ABORTED_STATUS, 'GM aborted'),
        (INFLIGHT_UNANCHORED_STATUS, 'Inflight unanchored'),
        (DESTROYED_STATUS, 'Destroyed'),
    )

    NONE_ACTIVITY = 0
    MANUFACTURING_ACTIVITY = 1
    RESEARCHING_TECHNOLOGY_ACTIVITY = 2
    RESEARCHING_TIME_ACTIVITY = 3
    RESEARCHING_MATERIAL_ACTIVITY = 4
    COPYING_ACTIVITY = 5
    DUPLICATING_ACTIVITY = 6
    REVERSE_ENGINEERING_ACTIVITY = 7
    INVENTION_ACTIVITY = 8
    ACTIVITY_CHOICES = (
        (NONE_ACTIVITY, 'None'),
        (MANUFACTURING_ACTIVITY, 'Manufacturing'),
        (RESEARCHING_TECHNOLOGY_ACTIVITY, 'Researching Technology'),
        (RESEARCHING_TIME_ACTIVITY, 'PE Research'),
        (RESEARCHING_MATERIAL_ACTIVITY, 'ME Research'),
        (COPYING_ACTIVITY, 'Copying'),
        (DUPLICATING_ACTIVITY, 'Duplicating'),
        (REVERSE_ENGINEERING_ACTIVITY, 'Reverse Engineering'),
        (INVENTION_ACTIVITY, 'Invention'),
    )

    character = models.ForeignKey(Character)
    corporation = models.ForeignKey(Corporation, blank=True, null=True)

    job_id = models.IntegerField()
    assembly_line_id = models.IntegerField()
    container_id = models.BigIntegerField()
    location_id = models.BigIntegerField()

    # asset ID?
    #item_id = models.IntegerField()
    item_productivity_level = models.IntegerField()
    item_material_level = models.IntegerField()

    output_location_id = models.BigIntegerField()
    installer_id = models.IntegerField()
    runs = models.IntegerField()
    licensed_production_runs_remaining = models.IntegerField()
    licensed_production_runs = models.IntegerField()

    system = models.ForeignKey(System)
    container_location_id = models.IntegerField()

    material_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    character_material_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    time_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    character_time_multiplier = models.DecimalField(max_digits=5, decimal_places=3)

    installed_item = models.ForeignKey(Item, related_name='job_installed_items')
    installed_flag = models.ForeignKey(InventoryFlag, related_name='job_installed_flags')
    output_item = models.ForeignKey(Item, related_name='job_output_items')
    output_flag = models.ForeignKey(InventoryFlag, related_name='job_output_flags')

    completed = models.IntegerField()
    completed_status = models.IntegerField(choices=STATUS_CHOICES)
    activity = models.IntegerField(choices=ACTIVITY_CHOICES)

    install_time = models.DateTimeField()
    begin_time = models.DateTimeField()
    end_time = models.DateTimeField()
    pause_time = models.DateTimeField()

    class Meta:
        app_label = 'thing'
        ordering = ('-end_time',)

# ------------------------------------------------------------------------------
