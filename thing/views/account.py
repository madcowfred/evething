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

import gzip
from cStringIO import StringIO

try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.contrib.auth.forms import UserCreationForm

from core.util import get_minimum_keyid
from thing.forms import UploadSkillPlanForm
from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8


@login_required
def account(request):
    """Account management view"""
    if 'message' in request.session:
        message = request.session.pop('message')
        message_type = request.session.pop('message_type')
    else:
        message = None
        message_type = None

    profile = request.user.profile

    characters = Character.objects.filter(apikeys__user=request.user).distinct()
    home_hide_characters = set(int(c) for c in profile.home_hide_characters.split(',') if c)

    return render_page(
        'thing/account.html',
        {
            'message': message,
            'message_type': message_type,
            'profile': profile,
            'home_chars_per_row': (2, 3, 4, 6),
            'home_sort_orders': UserProfile.HOME_SORT_ORDERS,
            'characters': characters,
            'home_hide_characters': home_hide_characters,
            'themes': settings.THEMES,
            'apikeys': APIKey.objects.filter(user=request.user).order_by('-valid', 'key_type', 'name'),
            'disable_password': getattr(settings, 'DISABLE_ACCOUNT_PASSWORD', False)
        },
        request,
        [c.id for c in characters],
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
def account_change_password(request):
    """Change password"""
    old_password = request.POST['old_password']
    new_password = request.POST['new_password']
    confirm_password = request.POST['confirm_password']

    # Password checks out ok
    if request.user.check_password(old_password):
        # New passwords match
        if new_password == confirm_password:
            # Length seems ok
            if len(new_password) >= 4:
                request.session['message_type'] = 'success'
                request.session['message'] = 'Password changed successfully.'

                request.user.set_password(new_password)
                request.user.save()
            # Too short
            else:
                request.session['message_type'] = 'error'
                request.session['message'] = 'Password must be at least 4 characters long!'
        # Passwords don't match
        else:
            request.session['message_type'] = 'error'
            request.session['message'] = 'New passwords do not match!'
    # Old password is incorrect
    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'Old password is incorrect!'

    return redirect('%s#password' % (reverse(account)))


@login_required
def account_settings(request):
    profile = request.user.profile

    theme = request.POST.get('theme', 'theme-default')
    if [t for t in settings.THEMES if t[0] == theme]:
        profile.theme = theme

    profile.show_clock = (request.POST.get('show_clock', '') == 'on')
    profile.show_assets = (request.POST.get('show_assets', '') == 'on')
    profile.show_blueprints = (request.POST.get('show_blueprints', '') == 'on')
    profile.show_contracts = (request.POST.get('show_contracts', '') == 'on')
    profile.show_industry = (request.POST.get('show_industry', '') == 'on')
    profile.show_orders = (request.POST.get('show_orders', '') == 'on')
    profile.show_trade = (request.POST.get('show_trade', '') == 'on')
    profile.show_transactions = (request.POST.get('show_transactions', '') == 'on')
    profile.show_wallet_journal = (request.POST.get('show_wallet_journal', '') == 'on')

    profile.show_item_icons = (request.POST.get('show_item_icons', '') == 'on')

    entries_per_page = request.POST.get('entries_per_page', '100')
    if entries_per_page not in ('100', '200', '300', '400', '500'):
        entries_per_page = '100'
    profile.entries_per_page = entries_per_page

    home_chars_per_row = int(request.POST.get('home_chars_per_row'), 0)
    if home_chars_per_row in (2, 3, 4, 6):
        profile.home_chars_per_row = home_chars_per_row

    home_sort_order = request.POST.get('home_sort_order')
    if [o for o in UserProfile.HOME_SORT_ORDERS if o[0] == home_sort_order]:
        profile.home_sort_order = home_sort_order

    profile.home_sort_descending = (request.POST.get('home_sort_descending', '') == 'on')
    profile.home_show_locations = (request.POST.get('home_show_locations', '') == 'on')
    profile.home_show_separators = (request.POST.get('home_show_separators', '') == 'on')
    profile.home_highlight_backgrounds = (request.POST.get('home_highlight_backgrounds', '') == 'on')
    profile.home_highlight_borders = (request.POST.get('home_highlight_borders', '') == 'on')
    profile.home_show_security = (request.POST.get('home_show_security', '') == 'on')

    # hide characters
    profile.home_hide_characters = ','.join(c for c in request.POST.getlist('home_hide_characters') if c.isdigit())

    profile.save()

    request.session['message_type'] = 'success'
    request.session['message'] = 'Settings changed successfully.'

    return redirect(account)


@login_required
def account_apikey_add(request):
    """Add an API key"""
    keyid = request.POST.get('keyid', '0')
    vcode = request.POST.get('vcode', '').strip()
    name = request.POST.get('name', '')
    group_name = request.POST.get('group_name', '')

    if not keyid.isdigit():
        request.session['message_type'] = 'error'
        request.session['message'] = 'KeyID is not an integer!'
    elif int(keyid) < 1 or int(keyid) > 2 ** 31:
        request.session['message_type'] = 'error'
        request.session['message'] = 'Invalid KeyID!'
    elif len(vcode) != 64:
        request.session['message_type'] = 'error'
        request.session['message'] = 'vCode must be 64 characters long!'
    elif int(keyid) < get_minimum_keyid():
        request.session['message_type'] = 'error'
        request.session['message'] = 'This key was created more than 30 minutes ago, make a new one for each app!'
    else:
        if request.user.profile.can_add_keys is False:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You are not allowed to add API keys!'

        elif APIKey.objects.filter(user=request.user, keyid=request.POST.get('keyid', 0)).count():
            request.session['message_type'] = 'error'
            request.session['message'] = 'You already have an API key with that KeyID!'

        else:
            apikey = APIKey(
                user_id=request.user.id,
                keyid=keyid,
                vcode=vcode,
                name=name,
                group_name=group_name,
            )
            apikey.save()

            request.session['message_type'] = 'success'
            request.session['message'] = 'API key added successfully!'

    return redirect('%s#apikeys' % (reverse(account)))


@login_required
def account_apikey_delete(request):
    """Delete an API key"""
    apikey_id = request.POST.get('apikey_id', '')
    if apikey_id.isdigit():
        try:
            apikey = APIKey.objects.get(user=request.user.id, id=apikey_id)

        except APIKey.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not have an API key with that KeyID!'

        else:
            request.session['message_type'] = 'success'
            request.session['message'] = 'API key %s deleted successfully!' % (apikey.id)

            apikey.delete()

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('%s#apikeys' % (reverse(account)))


@login_required
def account_apikey_edit(request):
    """Edit an API key"""
    try:
        apikey = APIKey.objects.get(user=request.user.id, id=request.POST.get('apikey_id', '0'))

    except APIKey.DoesNotExist:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You do not have an API key with that KeyID!'
    else:
        request.session['message_type'] = 'success'
        request.session['message'] = 'API key %s edited successfully!' % apikey.id

        apikey_name = request.POST.get('name', '')
        apikey_group_name = request.POST.get('group_name', '')
        dont_edit = request.POST.get('dont_edit', '')

        if apikey.name != apikey_name and dont_edit != 'name':
            apikey.name = apikey_name
            apikey.save()
        elif apikey.group_name != apikey_group_name and dont_edit != 'group_name':
            apikey.group_name = apikey_group_name
            apikey.save()

    return redirect('%s#apikeys' % (reverse(account)))


@login_required
def account_apikey_purge(request):
    """Purge an API key's data"""
    apikey_id = request.POST.get('apikey_id', '')
    if apikey_id.isdigit():
        try:
            apikey = APIKey.objects.get(user=request.user.id, id=apikey_id)

        except APIKey.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not have an API key with that KeyID!'

        else:
            request.session['message_type'] = 'success'
            request.session['message'] = 'API key %s purge queued successfully!' % (apikey.id)

            apikey.purge_data()

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('%s#apikeys' % (reverse(account)))




def account_register(request):
    """Register Account"""
    if not settings.ALLOW_REGISTRATION:
        return HttpResponseForbidden()

    if request.user.is_authenticated():
        return redirect(reverse('home'))

    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect(reverse('home'))
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {
        'form': form,
    })
