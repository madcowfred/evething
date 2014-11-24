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

import datetime

from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    """Profile information for a user"""
    HOME_SORT_ORDERS = (
        ('apiname', 'APIKey name'),
        ('charname', 'Character name'),
        ('corpname', 'Corporation name'),
        ('totalsp', 'Total SP'),
        ('wallet', 'Wallet balance'),
    )

    user = models.OneToOneField(User, related_name='profile')

    last_seen = models.DateTimeField(default=datetime.datetime.now)

    # User can add APIKeys
    can_add_keys = models.BooleanField(default=True)

    # Global options
    theme = models.CharField(max_length=32, default='default')
    show_clock = models.BooleanField(default=True)
    show_assets = models.BooleanField(default=True)
    show_blueprints = models.BooleanField(default=True)
    show_contracts = models.BooleanField(default=True)
    show_industry = models.BooleanField(default=True)
    show_orders = models.BooleanField(default=True)
    show_trade = models.BooleanField(default=True)
    show_transactions = models.BooleanField(default=True)
    show_wallet_journal = models.BooleanField(default=True)
    show_pi = models.BooleanField(default=True)

    show_item_icons = models.BooleanField(default=False)
    entries_per_page = models.IntegerField(default=100)

    # Home view options
    home_chars_per_row = models.IntegerField(default=4)
    home_sort_order = models.CharField(choices=HOME_SORT_ORDERS, max_length=12, default='apiname')
    home_sort_descending = models.BooleanField(default=False)
    home_hide_characters = models.TextField(default='', blank=True)
    home_show_locations = models.BooleanField(default=True)
    home_highlight_backgrounds = models.BooleanField(default=True)
    home_highlight_borders = models.BooleanField(default=True)
    home_show_separators = models.BooleanField(default=True)
    home_show_security = models.BooleanField(default=True)

    class Meta:
        app_label = 'thing'


def create_user_profile(sender, instance, created, **kwargs):
    """Magical hook to create a UserProfile when a User object is created"""
    if created:
        UserProfile.objects.create(user=instance)

models.signals.post_save.connect(create_user_profile, sender=User)
