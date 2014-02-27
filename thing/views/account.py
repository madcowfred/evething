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
from django.shortcuts import redirect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

from core.util import get_minimum_keyid
from thing.forms import UploadSkillPlanForm
from thing.models import *
from thing.stuff import *

# ---------------------------------------------------------------------------
# Account management view
@login_required
def account(request):
    if 'message' in request.session:
        message = request.session.pop('message')
        message_type = request.session.pop('message_type')
    else:
        message = None
        message_type = None

    profile = request.user.get_profile()

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
            'skillplans': SkillPlan.objects.filter(user=request.user),
            'visibilities': SkillPlan.VISIBILITY_CHOICES,
            'disable_password': getattr(settings, 'DISABLE_ACCOUNT_PASSWORD', False)
        },
        request,
        [c.id for c in characters],
    )

# ---------------------------------------------------------------------------
# Change password
@sensitive_post_parameters()
@sensitive_variables()
@login_required
def account_change_password(request):
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
    profile = request.user.get_profile()

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

    profile.save()

    request.session['message_type'] = 'success'
    request.session['message'] = 'Settings changed successfully.'

    return redirect(account)

@login_required
def account_home_page(request):
    profile = request.user.get_profile()

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

    profile.save()

    request.session['message_type'] = 'success'
    request.session['message'] = 'Settings changed successfully.'

    return redirect('%s#home_page' % (reverse(account)))

@login_required
def account_characters(request):
    profile = request.user.get_profile()

    # hide characters
    profile.home_hide_characters = ','.join(c for c in request.POST.getlist('home_hide_characters') if c.isdigit())
    profile.save()

    implants = [int(c) for c in request.POST.getlist('implants') if c.isdigit()]
    low_skill_queue = [int(c) for c in request.POST.getlist('low_skill_queue') if c.isdigit()]
    empty_skill_queue = [int(c) for c in request.POST.getlist('empty_skill_queue') if c.isdigit()]
    low_game_time = [int(c) for c in request.POST.getlist('low_game_time') if c.isdigit()]
    no_game_time = [int(c) for c in request.POST.getlist('no_game_time') if c.isdigit()]

    characters = Character.objects.filter(apikeys__user=request.user).distinct()
    for char in characters:
        char.config.home_suppress_implants = char.id in implants
        char.config.home_suppress_low_skill_queue = char.id in low_skill_queue
        char.config.home_suppress_empty_skill_queue = char.id in empty_skill_queue
        char.config.home_suppress_low_game_time = char.id in low_game_time
        char.config.home_suppress_no_game_time = char.id in no_game_time

        char.config.home_group = request.POST.get('group_' + str(char.id), '')

        char.config.save()


    return redirect('%s#characters' % (reverse(account)))

# ---------------------------------------------------------------------------
# Add an API key
@login_required
def account_apikey_add(request):
    keyid = request.POST.get('keyid', '0')
    vcode = request.POST.get('vcode', '').strip()
    name = request.POST.get('name', '')

    if not keyid.isdigit():
        request.session['message_type'] = 'error'
        request.session['message'] = 'KeyID is not an integer!'
    elif int(keyid) < 1 or int(keyid) > 2**31:
        request.session['message_type'] = 'error'
        request.session['message'] = 'Invalid KeyID!'
    elif len(vcode) != 64:
        request.session['message_type'] = 'error'
        request.session['message'] = 'vCode must be 64 characters long!'
    elif int(keyid) < get_minimum_keyid():
        request.session['message_type'] = 'error'
        request.session['message'] = 'This key was created more than 30 minutes ago, make a new one for each app!'
    else:
        if request.user.get_profile().can_add_keys is False:
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
            )
            apikey.save()

            request.session['message_type'] = 'success'
            request.session['message'] = 'API key added successfully!'

    return redirect('%s#apikeys' % (reverse(account)))

# ---------------------------------------------------------------------------
# Delete an API key
@login_required
def account_apikey_delete(request):
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

# ---------------------------------------------------------------------------
# Edit an API key
@login_required
def account_apikey_edit(request):
    try:
        apikey = APIKey.objects.get(user=request.user.id, id=request.POST.get('apikey_id', '0'))

    except APIKey.DoesNotExist:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You do not have an API key with that KeyID!'

    else:
        request.session['message_type'] = 'success'
        request.session['message'] = 'API key %s edited successfully!' % (apikey.id)

        apikey_name = request.POST.get('name', '')
        dont_edit = request.POST.get('dont_edit', '')

        if apikey.name != apikey_name and dont_edit != 'name':
            apikey.name = apikey_name
            apikey.save()

    return redirect('%s#apikeys' % (reverse(account)))

# ---------------------------------------------------------------------------
# Purge an API key's data
@login_required
def account_apikey_purge(request):
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

# ---------------------------------------------------------------------------
# Add a skillplan
@login_required
def account_skillplan_add(request):
    if request.method == 'POST':
        form = UploadSkillPlanForm(request.POST, request.FILES)
        if form.is_valid():
            _handle_skillplan_upload(request)
            return redirect('%s#skillplans' % (reverse(account)))
        else:
            request.session['message_type'] = 'error'
            request.session['message'] = 'Form validation failed!'
    else:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a POST request!"

    return redirect('%s#skillplans' % (reverse(account)))

# ---------------------------------------------------------------------------
# Delete a skillplan
@login_required
def account_skillplan_delete(request):
    skillplan_id = request.POST.get('skillplan_id', '')
    if skillplan_id.isdigit():
        try:
            skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)

        except SkillPlan.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not own that skill plan!'

        else:
            request.session['message_type'] = 'success'
            request.session['message'] = 'Skill plan "%s" deleted successfully!' % (skillplan.name)

            # Delete all of the random things for this skillplan
            entries = SPEntry.objects.filter(skill_plan=skillplan)
            SPRemap.objects.filter(pk__in=[e.sp_remap_id for e in entries if e.sp_remap_id]).delete()
            SPSkill.objects.filter(pk__in=[e.sp_skill_id for e in entries if e.sp_skill_id]).delete()
            entries.delete()
            skillplan.delete()

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('%s#skillplans' % (reverse(account)))

# ---------------------------------------------------------------------------
# Edit a skillplan
@login_required
def account_skillplan_edit(request):
    skillplan_id = request.POST.get('skillplan_id', '')
    if skillplan_id.isdigit():
        try:
            skillplan = SkillPlan.objects.get(user=request.user, id=skillplan_id)

        except SkillPlan.DoesNotExist:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You do not own that skill plan!'

        else:
            skillplan.name = request.POST['name']
            skillplan.visibility = request.POST['visibility']
            skillplan.save()

            request.session['message_type'] = 'success'
            request.session['message'] = 'Skill plan "%s" edited successfully!' % (skillplan.name)

    else:
        request.session['message_type'] = 'error'
        request.session['message'] = 'You seem to be doing silly things, stop that.'

    return redirect('%s#skillplans' % (reverse(account)))

# ---------------------------------------------------------------------------

def _handle_skillplan_upload(request):
    name = request.POST['name'].strip()
    uf = request.FILES['file']
    visibility = request.POST['visibility']

    # Check that this name is unique for the user
    if SkillPlan.objects.filter(user=request.user, name=name).count() > 0:
        request.session['message_type'] = 'error'
        request.session['message'] = "You already have a skill plan with that name!"
        return

    # Check file size, 10KB should be more than large enough
    if uf.size > 10240:
        request.session['message_type'] = 'error'
        request.session['message'] = "That file is too large!"
        return

    data = StringIO(uf.read())

    # Try opening it as a gzip file
    gf = gzip.GzipFile(fileobj=data)
    try:
        data = gf.read()
    except IOError:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a .EMP file!"
        return

    # Make sure it's valid XML
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a .EMP file!"
        return

    # FINALLY
    skillplan = SkillPlan.objects.create(
        user=request.user,
        name=name,
        visibility=visibility,
    )

    _parse_emp_plan(skillplan, root)

    request.session['message_type'] = 'success'
    request.session['message'] = "Skill plan uploaded successfully."


def _parse_emp_plan(skillplan, root):
    entries = []
    position = 0
    seen = {}

    for entry in root.findall('entry'):
        # Create the various objects for the remapping if it exists
        remapping = entry.find('remapping')
        if remapping is not None:
            # <remapping status="UpToDate" per="17" int="27" mem="21" wil="17" cha="17" description="" />
            spr = SPRemap.objects.create(
                int_stat=remapping.attrib['int'],
                mem_stat=remapping.attrib['mem'],
                per_stat=remapping.attrib['per'],
                wil_stat=remapping.attrib['wil'],
                cha_stat=remapping.attrib['cha'],
            )

            entries.append(SPEntry(
                skill_plan=skillplan,
                position=position,
                sp_remap=spr,
            ))

            position += 1

        # Grab some data we'll need
        skillID = int(entry.attrib['skillID'])
        level = int(entry.attrib['level'])
        priority = int(entry.attrib['priority'])

        # Get prereqs for this skill
        prereqs = Skill.get_prereqs(skillID)

        # Add any missing prereq skills
        for pre_skill_id, pre_level in prereqs:
            for i in range(seen.get(pre_skill_id, 0) + 1, pre_level + 1):
                try:
                    sps = SPSkill.objects.create(
                        skill_id=pre_skill_id,
                        level=i,
                        priority=priority,
                    )
                except:
                    continue

                entries.append(SPEntry(
                    skill_plan=skillplan,
                    position=position,
                    sp_skill=sps,
                ))

                position += 1
                seen[pre_skill_id] = i


        # Add the actual skill
        for i in range(seen.get(skillID, 0) + 1, level + 1):
            try:
                sps = SPSkill.objects.create(
                    skill_id=skillID,
                    level=i,
                    priority=priority,
                )
            except:
                continue

            entries.append(SPEntry(
                skill_plan=skillplan,
                position=position,
                sp_skill=sps,
            ))

            position += 1
            seen[skillID] = i

    SPEntry.objects.bulk_create(entries)

# ---------------------------------------------------------------------------
