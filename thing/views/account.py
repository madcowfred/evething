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
            'icon_themes': settings.ICON_THEMES,
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

    return redirect('%s#tab_password' % (reverse(account)))

@login_required
def account_settings(request):
    profile = request.user.get_profile()

    theme = request.POST.get('theme', 'theme-default')
    if [t for t in settings.THEMES if t[0] == theme]:
        profile.theme = theme
    
    icon_theme = request.POST.get('icon_theme', 'icons-default')
    if [t for t in settings.ICON_THEMES if t[0] == icon_theme]:
        profile.icon_theme = icon_theme

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

    # hide characters
    profile.home_hide_characters = ','.join(c for c in request.POST.getlist('home_hide_characters') if c.isdigit())

    profile.save()

    request.session['message_type'] = 'success'
    request.session['message'] = 'Settings changed successfully.'

    return redirect(account)

# ---------------------------------------------------------------------------
# Add an API key
@login_required
def account_apikey_add(request):
    keyid = request.POST.get('keyid', '0')
    vcode = request.POST.get('vcode', '')
    name = request.POST.get('name', '')

    if not keyid.isdigit():
        request.session['message_type'] = 'error'
        request.session['message'] = 'KeyID is not an integer!'
    elif int(keyid) < 1:
        request.session['message_type'] = 'error'
        request.session['message'] = 'KeyID must be >= 1!'
    elif len(vcode) != 64:
        request.session['message_type'] = 'error'
        request.session['message'] = 'vCode must be 64 characters long!'
    else:
        if APIKey.objects.filter(user=request.user, keyid=request.POST.get('keyid', 0)).count():
            request.session['message_type'] = 'error'
            request.session['message'] = 'You already have an API key with that KeyID!'

        elif request.user.get_profile().can_add_keys is False:
            request.session['message_type'] = 'error'
            request.session['message'] = 'You are not allowed to add API keys!'

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

    return redirect('%s#tab_apikeys' % (reverse(account)))

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

    return redirect('%s#tab_apikeys' % (reverse(account)))

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

        apikey.name = request.POST.get('name', '')
        apikey.save()

    return redirect('%s#tab_apikeys' % (reverse(account)))

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

    return redirect('%s#tab_apikeys' % (reverse(account)))

# ---------------------------------------------------------------------------
# Add a skillplan
@login_required
def account_skillplan_add(request):
    if request.method == 'POST':
        form = UploadSkillPlanForm(request.POST, request.FILES)
        if form.is_valid():
            _handle_skillplan_upload(request)
            return redirect('%s#tab_skillplans' % (reverse(account)))
        else:
            request.session['message_type'] = 'error'
            request.session['message'] = 'Form validation failed!'
    else:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a POST request!"

    return redirect('%s#tab_skillplans' % (reverse(account)))

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

    return redirect('%s#tab_skillplans' % (reverse(account)))

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

    return redirect('%s#tab_skillplans' % (reverse(account)))

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

        # Create the various objects for the skill
        try:
            sps = SPSkill.objects.create(
                skill_id=entry.attrib['skillID'],
                level=entry.attrib['level'],
                priority=entry.attrib['priority'],
            )
        except:
            continue
            
        entries.append(SPEntry(
            skill_plan=skillplan,
            position=position,
            sp_skill=sps,
        ))

        position += 1

    SPEntry.objects.bulk_create(entries)

# ---------------------------------------------------------------------------
