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
from thing.models.item import Item
from thing.models.blueprint import Blueprint
from thing.models.system import System


class IndustryJob(models.Model):
    """Industry job"""
    ACTIVE_STATUS = 1
    PAUSED_STATUS = 2
    CANCELLED_STATUS = 102
    DELIVERED_STATUS = 104
    FAILED_STATUS = 105
    UNKNOWN_STATUS = 999
    STATUS_CHOICES = (
        (ACTIVE_STATUS, 'Active'),
        (PAUSED_STATUS, 'Paused (Facility Offline)'),
        (CANCELLED_STATUS, 'Cancelled'),
        (DELIVERED_STATUS, 'Delivered'),
        (FAILED_STATUS, 'Failed'),
        (UNKNOWN_STATUS, 'Unknown')
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
        (RESEARCHING_TIME_ACTIVITY, 'TE Research'),
        (RESEARCHING_MATERIAL_ACTIVITY, 'ME Research'),
        (COPYING_ACTIVITY, 'Copying'),
        (DUPLICATING_ACTIVITY, 'Duplicating'),
        (REVERSE_ENGINEERING_ACTIVITY, 'Reverse Engineering'),
        (INVENTION_ACTIVITY, 'Invention'),
    )

    character = models.ForeignKey(Character)
    corporation = models.ForeignKey(Corporation, blank=True, null=True)

    job_id = models.IntegerField()
    installer_id = models.IntegerField()

    system = models.ForeignKey(System)
    activity = models.IntegerField(choices=ACTIVITY_CHOICES)
    blueprint = models.ForeignKey(Blueprint, related_name='job_installed_blueprints')
    output_location_id = models.BigIntegerField()
    runs = models.IntegerField()
    team_id = models.BigIntegerField()
    licensed_runs = models.IntegerField()
    product = models.ForeignKey(Item, related_name='job_products', null=True, blank=True)
    status = models.IntegerField(choices=STATUS_CHOICES)
    duration = models.IntegerField()

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    pause_date = models.DateTimeField()
    completed_date = models.DateTimeField()

    class Meta:
        app_label = 'thing'
        ordering = ('-end_date',)
