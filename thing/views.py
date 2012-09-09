import calendar
import datetime
import gzip
import operator
import re
from string import split
from django.db.models.query import QuerySet

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, InvalidPage, PageNotAnInteger
from django.core.urlresolvers import reverse
from django.db import connection
from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.http import Http404
from django.shortcuts import redirect, get_object_or_404
from django.template import RequestContext
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

from coffin.shortcuts import *

from thing import queries
from thing.forms import *
from thing.models import *
from thing.stuff import *
from thing.templatetags.thing_extras import commas, duration, shortduration

# ---------------------------------------------------------------------------
# How many days (10) to start warning about expiring accounts
ONE_DAY = 24 * 60 * 60
EXPIRE_WARNING = 10 * ONE_DAY

ORDER_SLOT_SKILLS = {
    'Trade': 4,
    'Retail': 8,
    'Wholesale': 16,
    'Tycoon': 32,
}

TWO_PLACES = Decimal('0.00')

# ---------------------------------------------------------------------------
# Home page
@login_required
def home(request):
    tt = TimerThing('home')

    # Create the user's profile if it doesn't already exist
    try:
        profile = request.user.get_profile()
    except UserProfile.DoesNotExist:
        profile = UserProfile(user=request.user)
        profile.save()

    tt.add_time('profile')

    now = datetime.datetime.utcnow()
    total_balance = 0

    # Make a set of characters to hide
    hide_characters = set(int(c) for c in profile.home_hide_characters.split(',') if c)

    # Initialise various data structures
    api_keys = set()
    training = set()
    chars = {}

    for apikey in APIKey.objects.prefetch_related('characters').filter(user=request.user).exclude(key_type=APIKey.CORPORATION_TYPE):
        api_keys.add(apikey)
        for char in apikey.characters.all():
            chars[char.id] = char
            char.z_apikey = apikey
            char.z_training = {}
            total_balance += char.wallet_balance

    tt.add_time('apikeys')

    # Do skill training check - this can't be in the model because it
    # scales like crap doing individual queries
    utcnow = datetime.datetime.utcnow()
    queues = SkillQueue.objects.select_related('character', 'skill__item').filter(character__in=chars, end_time__gte=utcnow)
    for sq in queues:
        char = chars[sq.character_id]
        if 'sq' not in char.z_training:
            char.z_training['sq'] = sq
            char.z_training['skill_duration'] = (sq.end_time - utcnow).total_seconds()
            char.z_training['sp_per_hour'] = int(sq.skill.get_sp_per_minute(char) * 60)
            char.z_training['complete_per'] = sq.get_complete_percentage(now)
            training.add(char.z_apikey)
        
        char.z_training['queue_duration'] = (sq.end_time - utcnow).total_seconds()

    tt.add_time('training')

    # Do total skill point aggregation
    total_sp = 0
    for cs in CharacterSkill.objects.select_related().filter(character__in=chars).values('character').annotate(total_sp=Sum('points')):
        chars[cs['character']].z_total_sp = cs['total_sp']
        total_sp += cs['total_sp']

    tt.add_time('total_sp')

    # Work out who is and isn't training
    not_training = api_keys - training

    # Do notifications
    for char_id, char in chars.items():
        char.z_notifications = []

        # Game time warnings
        if char.z_apikey.paid_until:
            timediff = (char.z_apikey.paid_until - now).total_seconds()

            if timediff < 0:
                char.z_notifications.append({
                    'icon': 'time-warning',
                    'text': 'Expired',
                    'tooltip': 'Game time has expired!',
                    'span_class': 'low-game-time',
                })

            elif timediff < EXPIRE_WARNING:
                char.z_notifications.append({
                    'icon': 'time-warning',
                    'text': shortduration(timediff),
                    'tooltip': 'Remaining game time is low!',
                    'span_class': 'low-game-time',
                })

        # Empty skill queue
        if char.z_apikey in not_training:
            char.z_notifications.append({
                'icon': 'queue-empty',
                'text': 'Empty!',
                'tooltip': 'Skill queue is empty!',
            })
        
        if char.z_training:
            # Room in skill queue
            if char.z_training['queue_duration'] < ONE_DAY:
                timediff = ONE_DAY - char.z_training['queue_duration']
                char.z_notifications.append({
                    'icon': 'queue-space',
                    'text': shortduration(timediff),
                    'tooltip': 'Skill queue is not full!',
                })

            # Missing implants
            skill = char.z_training['sq'].skill
            pri_attrs = Skill.ATTRIBUTE_MAP[skill.primary_attribute]
            sec_attrs = Skill.ATTRIBUTE_MAP[skill.secondary_attribute]
            pri_bonus = getattr(char, pri_attrs[1])
            sec_bonus = getattr(char, sec_attrs[1])

            if pri_bonus == 0 or sec_bonus == 0:
                t = []
                if pri_bonus == 0:
                    t.append(skill.get_primary_attribute_display())
                if sec_bonus == 0:
                    t.append(skill.get_secondary_attribute_display())

                char.z_notifications.append({
                    'icon': 'missing-implants',
                    'text': ', '.join(t),
                    'tooltip': 'Missing stat implants for currently training skill!',
                })

        # Insufficient clone
        if hasattr(char, 'z_total_sp') and char.z_total_sp > char.clone_skill_points:
            char.z_notifications.append({
                'icon': 'inadequate-clone',
                'text': '%s SP' % (commas(char.clone_skill_points)),
                'tooltip': 'Insufficient clone!',
            })

    tt.add_time('notifications')

    # Work out sort order
    char_list = chars.values()
    if profile.home_sort_order == 'apiname':
        temp = [(c.z_apikey.name, c.name.lower(), c) for c in char_list]
    elif profile.home_sort_order == 'charname':
        temp = [(c.name.lower(), c) for c in char_list]
    elif profile.home_sort_order == 'corpname':
        temp = [(c.corporation.name.lower(), c.name.lower(), c) for c in char_list]
    elif profile.home_sort_order == 'totalsp':
        temp = [(getattr(c, 'z_total_sp', 0), c) for c in char_list]
    elif profile.home_sort_order == 'wallet':
        temp = [(c.wallet_balance, c.name.lower(), c) for c in char_list]

    temp.sort()
    if profile.home_sort_descending:
        temp.reverse()

    char_list = [s[-1] for s in temp]
    
    tt.add_time('sort')

    # Make separate lists of training and not training characters
    first = [char for char in char_list if char.z_training and char.id not in hide_characters]
    last = [char for char in char_list if not char.z_training and char.id not in hide_characters]

    # Get corporations this user has APIKeys for
    corp_ids = APIKey.objects.select_related().filter(user=request.user.id).exclude(corp_character=None).values_list('corp_character__corporation', flat=True)
    corporations = Corporation.objects.filter(pk__in=corp_ids)

    # Get old event stats for staff users
    if request.user.is_staff:
        task_count = TaskState.objects.filter(state=TaskState.QUEUED_STATE).aggregate(Count('id'))['id__count']
    else:
        task_count = 0

    tt.add_time('misc junk')

    out = render_to_response(
        'thing/home.html',
        {
            'profile': profile,
            'not_training': not_training,
            'total_balance': total_balance,
            'total_sp': total_sp,
            'corporations': corporations,
            'characters': first + last,
            'events': Event.objects.filter(user=request.user)[:10],
            'task_count': task_count,
        },
        context_instance=RequestContext(request)
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# ---------------------------------------------------------------------------
# Various account stuff
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

    return render_to_response(
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
        context_instance=RequestContext(request)
    )

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
    profile.show_item_icons = (request.POST.get('show_item_icons', '') == 'on')
    profile.show_assets = (request.POST.get('show_assets', '') == 'on')
    profile.show_blueprints = (request.POST.get('show_blueprints', '') == 'on')
    profile.show_contracts = (request.POST.get('show_contracts', '') == 'on')
    profile.show_orders = (request.POST.get('show_orders', '') == 'on')
    profile.show_trade = (request.POST.get('show_trade', '') == 'on')
    profile.show_transactions = (request.POST.get('show_transactions', '') == 'on')
    profile.show_market_scan = (request.POST.get('show_market_scan', '') == 'on')

    home_chars_per_row = int(request.POST.get('home_chars_per_row'), 0)
    if home_chars_per_row in (2, 3, 4, 6):
        profile.home_chars_per_row = home_chars_per_row

    home_sort_order = request.POST.get('home_sort_order')
    if [o for o in UserProfile.HOME_SORT_ORDERS if o[0] == home_sort_order]:
        profile.home_sort_order = home_sort_order

    profile.home_sort_descending = (request.POST.get('home_sort_descending', '') == 'on')

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
# Add a skillplan
@login_required
def account_skillplan_add(request):
    if request.method == 'POST':
        form = UploadSkillPlanForm(request.POST, request.FILES)
        if form.is_valid():
            handle_skillplan_upload(request)
            return redirect('%s#tab_skillplans' % (reverse(account)))
        else:
            request.session['message_type'] = 'error'
            request.session['message'] = 'Form validation failed!'
    else:
        request.session['message_type'] = 'error'
        request.session['message'] = "That doesn't look like a POST request!"

    return redirect('%s#tab_skillplans' % (reverse(account)))

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
# Assets
@login_required
def assets(request):
    tt = TimerThing('assets')

    character_ids = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    characters = Character.objects.in_bulk(character_ids)
    
    corporation_ids = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))
    corporations = Corporation.objects.in_bulk(corporation_ids)

    # apply our initial set of filters
    #assets = Asset.objects.select_related('system', 'station', 'inv_flag')
    assets = Asset.objects.filter(
        Q(character__in=character_ids, corporation_id__isnull=True)
        |
        Q(corporation_id__in=corporation_ids)
    )
    #assets = assets.distinct()

    tt.add_time('init')
    # retrieve any supplied search values
    f_search = request.GET.getlist('search')
    
    if len(f_search) == 1:
        search = f_search[0]
        query=Q()
        for word in split(search, ' '):
            query = query &( Q(character__name__icontains = word) |
            Q(character__corporation__name__icontains  = word) |
            Q(system__name__icontains = word) |
            Q(system__constellation__region__name = word) |
            Q(station__system__constellation__region__name__icontains = word) |
            Q(station__system__name__icontains = word) |
            Q(station__name__icontains = word) |
            Q(item__name__icontains = word) |
            Q(name__icontains = word) |
            Q(parent__isnull = False)) #keeps the childs
            assets = assets.filter(query)
    else:
        search=""

    tt.add_time('filters')

    # gather data for bulk fetching
    inv_flag_ids = set()
    item_ids = set()
    station_ids = set()
    system_ids = set()

    for asset in assets:
        inv_flag_ids.add(asset.inv_flag_id)
        item_ids.add(asset.item_id)
        if asset.station_id is not None:
            station_ids.add(asset.station_id)
        if asset.system_id is not None:
            system_ids.add(asset.system_id)

    tt.add_time('assets prep')

    inv_flag_map = InventoryFlag.objects.in_bulk(inv_flag_ids)
    tt.add_time('bulk invflag')
    item_map = Item.objects.select_related().in_bulk(item_ids)
    tt.add_time('bulk item')
    station_map = Station.objects.in_bulk(station_ids)
    tt.add_time('bulk station')
    system_map = System.objects.in_bulk(system_ids)
    tt.add_time('bulk system')

    # initialise data structures
    ca_lookup = {}
    loc_totals = {}
    systems = {}

    #print len(asset_list)
    for ca in assets:
        ca.z_inv_flag = inv_flag_map[ca.inv_flag_id]
        ca.z_item = item_map[ca.item_id]

        # character and corporation
        ca.z_character = characters[ca.character_id]
        ca.z_corporation = corporations.get(ca.corporation_id)

        # work out if this is a system or station asset
        k = getattr(station_map.get(ca.station_id, system_map.get(ca.system_id)), 'name', None)

        # zz blueprints
        if ca.z_item.item_group.category.name == 'Blueprint':
            ca.z_blueprint = min(-1, ca.raw_quantity)
        else:
            ca.z_blueprint = 0
        
        # total value of this asset stack
        if ca.z_blueprint >= 0:
            # capital ship, calculate build cost
            if ca.z_item.item_group.name in ('Carrier', 'Dreadnought', 'Supercarrier', 'Titan'):
                ca.z_capital = True
            ca.z_price = ca.z_item.sell_price
        # BPOs use the base price
        elif ca.z_blueprint == -1:
            ca.z_price = ca.z_item.base_price
        # BPCs count as 0 value
        else:
            ca.z_price = 0
        
        ca.z_total = ca.quantity * ca.z_price

        # system/station asset
        if k is not None:
            ca_lookup[ca.id] = ca

            ca.z_k = k
            ca.z_contents = []

            if k not in systems:
                loc_totals[k] = 0
                systems[k] = []
            
            loc_totals[k] += ca.z_total
            systems[k].append(ca)

        # asset is inside something, assign it to parent
        else:
            parent = ca_lookup.get(ca.parent_id, None)
            if parent is None:
                continue

            # add to parent's contents
            parent.z_contents.append(ca)

            # add this to the parent's entry in loc_totals
            loc_totals[parent.z_k] += ca.z_total
            parent.z_total += ca.z_total

            # Celestials (containers) need some special casing
            if parent.z_item.item_group.category.name == 'Celestial':
                ca.z_locked = (ca.z_inv_flag.name == 'Locked')

                ca.z_group = ca.z_item.item_group.category.name

            else:
                # inventory group
                ca.z_group = ca.z_inv_flag.nice_name()
                # corporation hangar
                if ca.z_corporation is not None and ca.z_group.startswith('CorpSAG'):
                    ca.z_group = getattr(ca.z_corporation, 'division%s' % (ca.z_group[-1]))

    tt.add_time('main loop')

    # add contents to the parent total
    for cas in systems.values():
        for ca in cas:
            if hasattr(ca, 'z_contents'):
                #for content in ca.z_contents:
                #    ca.z_total += content.z_total

                # decorate/sort/undecorate argh
                temp = [(c.z_inv_flag.sort_order(), c.z_item.name, c) for c in ca.z_contents]
                temp.sort()
                ca.z_contents = [s[2] for s in temp]

                ca.z_mod = len(ca.z_contents) % 2

    tt.add_time('parents')

    # get a total asset value
    total_value = sum(loc_totals.values())

    # decorate/sort/undecorate for our strange sort requirements :(
    for system_name in systems:
        temp = [(ca.z_character.name.lower(), ca.is_leaf_node(), ca.z_item.name, ca.name, ca) for ca in systems[system_name]]
        temp.sort()
        systems[system_name] = [s[-1] for s in temp]

    sorted_systems = sorted(systems.items())

    tt.add_time('sort')

    out = render_to_response(
        'thing/assets.html',
        {
            'characters': characters,
            'corporations': corporations,
            'search'   : search,
            'total_value': total_value,
            'systems': sorted_systems,
            'loc_totals': loc_totals,
        },
        context_instance=RequestContext(request)
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# ---------------------------------------------------------------------------
# List of blueprints we own
@login_required
def blueprints(request):
    # Get a valid number of runs
    try:
        runs = int(request.GET.get('runs', '1'))
    except ValueError:
        runs = 1
    
    # Build a map of Blueprint.id -> BlueprintComponent
    bpc_map = {}
    bp_ids = BlueprintInstance.objects.filter(user=request.user.id).values_list('blueprint_id', flat=True)
    for bpc in BlueprintComponent.objects.select_related(depth=1).filter(blueprint__in=bp_ids):
        bpc_map.setdefault(bpc.blueprint.id, []).append(bpc)
    
    # Assemble blueprint data
    bpis = []
    for bpi in BlueprintInstance.objects.select_related().filter(user=request.user.id):
        # Cache component list so we don't have to retrieve it multiple times
        components = bpi._get_components(components=bpc_map[bpi.blueprint.id], runs=runs)
        
        # Calculate a bunch of things we can't easily do via SQL
        bpi.z_count = bpi.blueprint.item.portion_size * runs
        bpi.z_production_time = bpi.calc_production_time(runs=runs)
        bpi.z_unit_cost_buy = bpi.calc_production_cost(components=components, runs=runs)
        bpi.z_unit_profit_buy = bpi.blueprint.item.sell_price - bpi.z_unit_cost_buy
        bpi.z_unit_cost_sell = bpi.calc_production_cost(runs=runs, use_sell=True, components=components)
        bpi.z_unit_profit_sell = bpi.blueprint.item.sell_price - bpi.z_unit_cost_sell
        
        bpis.append(bpi)
    
    # Render template
    return render_to_response(
        'thing/blueprints.html',
        {
            'blueprints': Blueprint.objects.all(),
            'bpis': bpis,
            'runs': runs,
        },
        context_instance=RequestContext(request)
    )

# Add a new blueprint
@login_required
def blueprints_add(request):
    bpi = BlueprintInstance(
        user=request.user,
        blueprint_id=request.GET['blueprint_id'],
        original=request.GET.get('original', False),
        material_level=request.GET['material_level'],
        productivity_level=request.GET['productivity_level'],
    )
    bpi.save()
    
    return redirect('blueprints')

@login_required
def blueprints_del(request):
    bpi = get_object_or_404(BlueprintInstance, user=request.user, pk=request.GET['bpi_id'])
    bpi.delete()

    return redirect('blueprints')

@login_required
def blueprints_edit(request):
    bpi = get_object_or_404(BlueprintInstance, user=request.user, pk=request.GET['bpi_id'])
    bpi.material_level = request.GET['new_ml']
    bpi.productivity_level = request.GET['new_pl']
    bpi.save()

    return redirect('blueprints')

# ---------------------------------------------------------------------------
# Calculate blueprint production details for X number of days
@login_required
def bpcalc(request):
    # Get a valid number of days
    try:
        days = max(1, int(request.GET.get('days', '7')))
    except ValueError:
        days = 7

    # Initialise variabls
    bpis = []
    bpi_totals = {
        'input_m3': Decimal('0.0'),
        'output_m3': Decimal('0.0'),
        'total_sell': Decimal('0.0'),
        'buy_build': Decimal('0.0'),
        'buy_profit': Decimal('0.0'),
        'sell_build': Decimal('0.0'),
        'sell_profit': Decimal('0.0'),
    }
    component_list = []
    comp_totals = {
        'volume': 0,
        'buy_total': 0,
        'sell_total': 0,
    }
    
    # Get the list of BPIs from GET vars
    bpi_list = map(int, request.GET.getlist('bpi'))
    if bpi_list:
        # Build a map of Blueprint.id -> BlueprintComponents
        bpc_map = {}
        bp_ids = BlueprintInstance.objects.filter(user=request.user.id, pk__in=bpi_list).values_list('blueprint_id', flat=True)
        for bpc in BlueprintComponent.objects.select_related(depth=1).filter(blueprint__in=bp_ids):
            bpc_map.setdefault(bpc.blueprint.id, []).append(bpc)
        
        # Do weekly movement in bulk
        item_ids = list(BlueprintInstance.objects.filter(user=request.user.id, pk__in=bpi_list).values_list('blueprint__item_id', flat=True))
        one_month_ago = datetime.datetime.utcnow() - datetime.timedelta(30)
        
        if item_ids:
            query = queries.bpcalc_movement % (', '.join(map(str, item_ids)))
            
            cursor = connection.cursor()
            cursor.execute(query, (days, one_month_ago,))
            move_map = {}
            for row in cursor:
                move_map[row[0]] = row[1]
            
            comps = {}
            # Fetch BlueprintInstance objects
            for bpi in BlueprintInstance.objects.select_related('blueprint__item').filter(user=request.user.id, pk__in=bpi_list):
                # Skip BPIs with no current price information
                if bpi.blueprint.item.sell_price == 0 and bpi.blueprint.item.buy_price == 0:
                    continue
                
                # Work out how many runs fit into the number of days provided
                pt = bpi.calc_production_time()
                runs = int((ONE_DAY * days) / pt)
                
                # Skip really long production items
                if runs == 0:
                    continue
                
                built = runs * bpi.blueprint.item.portion_size
                
                # Magical m3 stuff
                bpi.z_input_m3 = 0
                bpi.z_output_m3 = bpi.blueprint.item.volume * built

                # Add the components
                components = bpi._get_components(components=bpc_map[bpi.blueprint.id], runs=runs)
                for item, amt in components:
                    comps[item] = comps.get(item, 0) + amt
                    bpi.z_input_m3 += (item.volume * amt)

                # Calculate a bunch of things we can't easily do via SQL
                bpi.z_total_time = pt * runs
                bpi.z_runs = runs
                bpi.z_built = built
                bpi.z_total_sell = bpi.blueprint.item.sell_price * built
                bpi.z_buy_build = bpi.calc_production_cost(runs=runs, components=components) * built
                bpi.z_sell_build = bpi.calc_production_cost(runs=runs, use_sell=True, components=components) * built
                
                bpi.z_buy_profit = bpi.z_total_sell - bpi.z_buy_build
                bpi.z_buy_profit_per = (bpi.z_buy_profit / bpi.z_buy_build * 100).quantize(Decimal('.1'))
                bpi.z_sell_profit = bpi.z_total_sell - bpi.z_sell_build
                bpi.z_sell_profit_per = (bpi.z_sell_profit / bpi.z_sell_build * 100).quantize(Decimal('.1'))
                
                #bpi.z_volume_week = bpi.blueprint.item.get_volume()
                bpi.z_volume_week = move_map.get(bpi.blueprint.item.id, 0)
                if bpi.z_volume_week:
                    bpi.z_volume_percent = (bpi.z_built / bpi.z_volume_week * 100).quantize(Decimal('.1'))

                # Update totals
                bpi_totals['input_m3'] += bpi.z_input_m3
                bpi_totals['output_m3'] += bpi.z_output_m3
                bpi_totals['total_sell'] += bpi.z_total_sell
                bpi_totals['buy_build'] += bpi.z_buy_build
                bpi_totals['buy_profit'] += bpi.z_buy_profit
                bpi_totals['sell_build'] += bpi.z_sell_build
                bpi_totals['sell_profit'] += bpi.z_sell_profit
                
                bpis.append(bpi)
            
            # Components
            for item, amt in comps.items():
                component_list.append({
                    'item': item,
                    'amount': amt,
                    'volume': (amt * item.volume).quantize(Decimal('.1')),
                    'buy_total': amt * item.buy_price,
                    'sell_total': amt * item.sell_price,
                })
            component_list.sort(key=lambda c: c['item'].name)
            
            # Do some sums
            if bpi_totals['buy_profit'] and bpi_totals['buy_build']:
                bpi_totals['buy_profit_per'] = (bpi_totals['buy_profit'] / bpi_totals['buy_build'] * 100).quantize(Decimal('.1'))
            if bpi_totals['sell_profit'] and bpi_totals['sell_build']:
                bpi_totals['sell_profit_per'] = (bpi_totals['sell_profit'] / bpi_totals['sell_build'] * 100).quantize(Decimal('.1'))
            
            comp_totals['volume'] = sum(comp['volume'] for comp in component_list)
            comp_totals['buy_total'] = sum(comp['buy_total'] for comp in component_list)
            comp_totals['sell_total'] = sum(comp['sell_total'] for comp in component_list)
        
    # Render template
    return render_to_response(
        'thing/bpcalc.html',
        {
            'bpis': bpis,
            'bpi_totals': bpi_totals,
            'components': component_list,
            'comp_totals': comp_totals,
            'days': days,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Display a character page
def character(request, character_name):
    queryset = Character.objects.select_related('config', 'corporation__alliance')
    char = get_object_or_404(queryset, name=character_name)

    # Check access
    public = True
    if request.user.is_authenticated() and char.apikeys.filter(user=request.user):
        public = False

    # Check for CharacterConfig, creating an empty config if it does not exist
    if char.config is None:
        config = CharacterConfig(character=char)
        config.save()

        char.config = config
        char.save()

    # If it's for public access, make sure this character is visible
    if public and not char.config.is_public:
        raise Http404

    return character_common(request, char, public=public)

# Display an anonymized character page
def character_anonymous(request, anon_key):
    char = get_object_or_404(Character.objects.select_related('config'), config__anon_key=anon_key)

    return character_common(request, char, anonymous=True)

# Common code for character views
def character_common(request, char, public=True, anonymous=False):
    tt = TimerThing('character_common')

    # Retrieve skill queue
    queue = SkillQueue.objects.select_related('skill__item', 'character__corporation').filter(character=char, end_time__gte=datetime.datetime.utcnow()).order_by('end_time')
    if (public is False or anonymous is True or char.config.show_skill_queue) and queue:
        training_id = queue[0].skill.item.id
        training_level = queue[0].to_level
        for sq in queue:
            queue_duration = (sq.end_time - datetime.datetime.utcnow()).total_seconds()
    else:
        training_id = None
        training_level = None
        queue_duration = None

    tt.add_time('skill queue')

    # Retrieve the list of skills and group them by market group
    skills = OrderedDict()
    skill_totals = {}
    cur = None

    # Fake MarketGroup for unpublished skills
    total_sp = 0

    unpub_mg = MarketGroup(id=0, name="Unpublished")
    unpub_mg.z_total_sp = 0
    skills[unpub_mg] = []

    for cs in CharacterSkill.objects.select_related('skill__item__market_group').filter(character=char).order_by('skill__item__market_group__name', 'skill__item__name'):
        mg = cs.skill.item.market_group or unpub_mg
        if mg != cur:
            cur = mg
            cur.z_total_sp = 0
            skills[cur] = []

        cs.z_icons = []
        # level 5 skill = 5 special icons
        if cs.level == 5:
            cs.z_icons.extend(['fives'] * 5)
            cs.z_class = "level5"
        # 0-4 = n icons
        else:
            cs.z_icons.extend(['trained'] * cs.level)

        # training skill can have a training icon
        if anonymous is False and cs.skill.item.id == training_id:
            cs.z_icons.append('partial')
            cs.z_training = True
            cs.z_class = "training-highlight"

        # partially trained skills get a partial icon
        elif cs.points > cs.skill.get_sp_at_level(cs.level):
            cs.z_icons.append('partial')

        # then fill out the rest with empty icons
        cs.z_icons.extend(['untrained'] * (5 - len(cs.z_icons)))

        skills[cur].append(cs)
        cur.z_total_sp += cs.points
        total_sp += cs.points

    # Move the fake MarketGroup to the end if it has any skills
    k, v = skills.popitem(False)
    if v:
        skills[k] = v

    tt.add_time('skill group')

    # Retrieve skillplans
    user_ids = APIKey.objects.filter(characters__name=char.name).values_list('user_id', flat=True)

    if anonymous is False and request.user.is_authenticated():
        plans = SkillPlan.objects.filter(
            Q(user=request.user)
            |
            Q(visibility=SkillPlan.GLOBAL_VISIBILITY)
        )
        # |
        # (
        #     Q(user__in=user_ids)
        #     &
        #     Q(visibility=SkillPlan.PUBLIC_VISIBILITY)
        # )
    else:
        plans = SkillPlan.objects.filter(visibility=SkillPlan.GLOBAL_VISIBILITY)

    # Sort out the plans and apply icon states
    user_plans = []
    public_plans = []
    for sp in plans:
        if sp.visibility == SkillPlan.PRIVATE_VISIBILITY:
            sp.z_icon = 'private'
        elif sp.visibility == SkillPlan.PUBLIC_VISIBILITY:
            sp.z_icon = 'public'
        elif sp.visibility == SkillPlan.GLOBAL_VISIBILITY:
            sp.z_icon = 'global'

        if sp.user_id == request.user.id:
            user_plans.append(sp)
        else:
            public_plans.append(sp)

    tt.add_time('skill plans')

    # Do various visibility things here instead of in awful template code
    show = {
        'implants': not anonymous and (not public or char.config.show_implants),
        'queue': queue and (anonymous or not public or char.config.show_skill_queue),
        'standings': not anonymous and (not public or char.config.show_standings),
        'wallet': not anonymous and (not public or char.config.show_wallet),
    }

    if show['standings']:
        faction_standings = list(char.factionstanding_set.select_related().all())
        corp_standings = list(char.corporationstanding_set.select_related().all())
    else:
        faction_standings = []
        corp_standings = []

    # Render template
    out = render_to_response(
        'thing/character.html',
        {
            'char': char,
            'public': public,
            'anonymous': anonymous,
            'show': show,
            'total_sp': total_sp,
            'skills': skills,
            'skill_totals': skill_totals,
            'queue': queue,
            'queue_duration': queue_duration,
            'user_plans': user_plans,
            'public_plans': public_plans,
            'faction_standings': faction_standings,
            'corp_standings': corp_standings,
        },
        context_instance=RequestContext(request)
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

ANON_KEY_RE = re.compile(r'^[a-z0-9]+$')
@login_required
def character_settings(request, character_name):
    chars = Character.objects.filter(name=character_name, apikeys__user=request.user).distinct()
    if chars.count() == 0:
        raise Http404
    char = chars[0]

    char.config.is_public = ('public' in request.POST)
    char.config.show_clone = ('clone' in request.POST)
    char.config.show_implants = ('implants' in request.POST)
    char.config.show_skill_queue = ('queue' in request.POST)
    char.config.show_standings = ('standings' in request.POST)
    char.config.show_wallet = ('wallet' in request.POST)

    if 'anon-key-toggle' in request.POST:
        anon_key = request.POST.get('anon-key', '').lower()
        if ANON_KEY_RE.match(anon_key) and len(anon_key) == 16:
            char.config.anon_key = anon_key
        else:
            char.config.anon_key = None
    else:
        char.config.anon_key = None

    char.config.save()

    return redirect(char)

# ---------------------------------------------------------------------------
# Display a SkillPlan for a character
def character_skillplan(request, character_name, skillplan_id):
    user_ids = APIKey.objects.filter(characters__name=character_name).values_list('user_id', flat=True)

    public = True

    # If the user is logged in, check if the character belongs to them
    if request.user.is_authenticated():
        chars = Character.objects.filter(name=character_name, apikeys__user=request.user).distinct()
        if chars.count() == 1:
            character = chars[0]
            public = False
            qs = Q(visibility=SkillPlan.GLOBAL_VISIBILITY) | Q(user=request.user) | (Q(user__in=user_ids) & Q(visibility=SkillPlan.PUBLIC_VISIBILITY))
            skillplan = get_object_or_404(SkillPlan.objects.prefetch_related('entries'), qs, pk=skillplan_id)

    # Not logged in or character does not belong to user
    if public is True:
        character = get_object_or_404(Character, name=character_name, config__is_public=True)
        
        qs = Q(visibility=SkillPlan.GLOBAL_VISIBILITY) | (Q(user__in=user_ids) & Q(visibility=SkillPlan.PUBLIC_VISIBILITY))
        if request.user.is_authenticated():
            qs |= Q(user=request.user)
        skillplan = get_object_or_404(SkillPlan.objects.prefetch_related('entries'), qs, pk=skillplan_id)

    return character_skillplan_common(request, character, skillplan, public=public)

# Display a SkillPlan for an anonymous character
def character_anonymous_skillplan(request, anon_key, skillplan_id):
    character = get_object_or_404(Character.objects.select_related('config'), config__anon_key=anon_key)
    skillplan = get_object_or_404(SkillPlan.objects.prefetch_related('entries'), pk=skillplan_id, visibility=SkillPlan.GLOBAL_VISIBILITY)

    return character_skillplan_common(request, character, skillplan, anonymous=True)

def character_skillplan_common(request, character, skillplan, public=True, anonymous=False):
    tt = TimerThing('skillplan_common')

    utcnow = datetime.datetime.utcnow()

    implants_visible = not public

    # Check our GET variables
    implants = request.GET.get('implants', '')
    if implants.isdigit() and 0 <= int(implants) <= 5:
        implants = int(implants)
    elif implants_visible is True:
        implants = 0
    else:
        implants = 3

    show_trained = ('show_trained' in request.GET)

    tt.add_time('init')

    # Build a CharacterSkill lookup dictionary
    learned = {}
    for cs in CharacterSkill.objects.filter(character=character).select_related('skill__item'):
        learned[cs.skill.item.id] = cs

    tt.add_time('char skills')

    # Possibly get training information
    training_skill = None
    if anonymous is True or public is False or character.config.show_skill_queue is True:
        sqs = list(SkillQueue.objects.select_related('skill__item').filter(character=character, end_time__gte=utcnow))
        if sqs:
            training_skill = sqs[0]

    tt.add_time('training')

    # Initialise stat stuff
    remap_stats = dict(
        int_attribute=character.int_attribute,
        mem_attribute=character.mem_attribute,
        per_attribute=character.per_attribute,
        wil_attribute=character.wil_attribute,
        cha_attribute=character.cha_attribute,
    )
    implant_stats = {}
    for stat in ('int', 'mem', 'per', 'wil', 'cha'):
        k = '%s_bonus' % (stat)
        if implants == 0 and implants_visible is True:
            implant_stats[k] = getattr(character, k)
        else:
            implant_stats[k] = implants

    # Iterate over all entries in this skill plan
    entries = []
    total_remaining = 0.0
    for entry in skillplan.entries.select_related('sp_remap', 'sp_skill__skill__item__item_group'):
        # It's a remap entry
        if entry.sp_remap is not None:
            # Delete the previous remap if it's two in a row, that makes no sense
            if entries and entries[-1].sp_remap is not None:
                entries.pop()

            remap_stats['int_attribute'] = entry.sp_remap.int_stat
            remap_stats['mem_attribute'] = entry.sp_remap.mem_stat
            remap_stats['per_attribute'] = entry.sp_remap.per_stat
            remap_stats['wil_attribute'] = entry.sp_remap.wil_stat
            remap_stats['cha_attribute'] = entry.sp_remap.cha_stat

        # It's a skill entry
        if entry.sp_skill is not None:
            skill = entry.sp_skill.skill

            # If this skill is already learned
            cs = learned.get(skill.item.id, None)
            if cs is not None:
                # Mark it as injected if level 0
                if cs.level == 0:
                    entry.z_injected = True
                # It might already be trained
                elif cs.level >= entry.sp_skill.level:
                    # If we don't care about trained skills, skip this skill entirely
                    if not show_trained:
                        continue

                    entry.z_trained = True
            # Not learned, need to buy it
            else:
                entry.z_buy = True

            # Calculate SP/hr
            if remap_stats:
                entry.z_sppm = skill.get_sppm_stats(remap_stats, implant_stats)
            else:
                if public is True or anonymous is True:
                    entry.z_sppm = skill.get_sp_per_minute(character, implants=implant_stats)
                else:
                    entry.z_sppm = skill.get_sp_per_minute(character)
            
            # 0 sppm is bad
            entry.z_sppm = max(1, entry.z_sppm)
            entry.z_spph = int(entry.z_sppm * 60)

            # Calculate time remaining
            if training_skill is not None and training_skill.skill_id == entry.sp_skill.skill_id and training_skill.to_level == entry.sp_skill.level:
                entry.z_remaining = (training_skill.end_time - utcnow).total_seconds()
                entry.z_training = True
            else:
                entry.z_remaining = (skill.get_sp_at_level(entry.sp_skill.level) - skill.get_sp_at_level(entry.sp_skill.level - 1)) / entry.z_sppm * 60

            # Add time remaining to total
            if not hasattr(entry, 'z_trained'):
                total_remaining += entry.z_remaining

        entries.append(entry)

    tt.add_time('skillplan loop')

    out = render_to_response(
        'thing/character_skillplan.html',
        {
            'show_trained': show_trained,
            'implants': implants,
            'implants_visible': implants_visible,
            'anonymous': anonymous,
            'char': character,
            'skillplan': skillplan,
            'entries': entries,
            'total_remaining': total_remaining,
        },
        context_instance=RequestContext(request)
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

# ---------------------------------------------------------------------------
# Contracts
@login_required
def contracts(request):
    characters = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    corporations = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))

    # Whee~
    contracts = Contract.objects.select_related('issuer_char', 'issuer_corp', 'start_station', 'end_station')
    contracts = contracts.filter(
        (
            (
                Q(issuer_char_id__in=characters) |
                Q(assignee_id__in=characters) |
                Q(acceptor_id__in=characters)
            )
            &
            Q(for_corp=False)
        )
        |
        (
            (
                Q(issuer_corp_id__in=corporations) |
                Q(assignee_id__in=corporations) |
                Q(acceptor_id__in=corporations)
            )
            &
            Q(for_corp=True)
        )
    )

    lookup_ids = set()
    for contract in contracts:
        # Assign a status icon to each contract
        if contract.status.startswith('Completed'):
            contract.z_status_icon = 'completed'
        elif contract.status == 'InProgress':
            contract.z_status_icon = 'inprogress'
        elif contract.status in ('Cancelled', 'Deleted', 'Failed', 'Rejected'):
            contract.z_status_icon = 'failed'
        elif contract.status == 'Outstanding':
            contract.z_status_icon = 'outstanding'
        else:
            contract.z_status_icon = 'unknown'

        # Add the ids to the lookup set
        if contract.assignee_id:
            lookup_ids.add(contract.assignee_id)
        if contract.acceptor_id:
            lookup_ids.add(contract.acceptor_id)

    # Do some lookups
    char_map = SimpleCharacter.objects.in_bulk(lookup_ids)
    corp_map = Corporation.objects.in_bulk(lookup_ids)
    alliance_map = Alliance.objects.in_bulk(lookup_ids)

    # Now attach those to each contract
    for contract in contracts:
        if contract.assignee_id:
            # Assignee
            char = char_map.get(contract.assignee_id, None)
            if char is not None:
                contract.z_assignee_char = char

            corp = corp_map.get(contract.assignee_id, None)
            if corp is not None:
                contract.z_assignee_corp = corp
            
            alliance = alliance_map.get(contract.assignee_id, None)
            if alliance is not None:
                contract.z_assignee_alliance = alliance

            # Acceptor
            char = char_map.get(contract.acceptor_id, None)
            if char is not None:
                contract.z_acceptor_char = char

            corp = corp_map.get(contract.acceptor_id, None)
            if corp is not None:
                contract.z_acceptor_corp = corp


    return render_to_response(
        'thing/contracts.html',
        dict(
            characters=characters,
            contracts=contracts,
            char_map=char_map,
            corp_map=corp_map,
            alliance_map=alliance_map,
        ),
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Events
@login_required
def events(request):
    # Get a QuerySet of events for this user
    events = Event.objects.filter(user=request.user)

    # Create a new paginator
    paginator = Paginator(events, 100)
    
    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        events = paginator.page(page)
    except (EmptyPage, InvalidPage):
        events = paginator.page(paginator.num_pages)
    
    # Render template
    return render_to_response(
        'thing/events.html',
        {
            'events': events,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Market scan
@login_required
def market_scan(request):
    cursor = connection.cursor()
    cursor.execute(queries.user_item_ids, (request.user.id, request.user.id, request.user.id))

    item_ids = []
    for row in cursor:
        item_ids.append(row[0])

    return render_to_response(
        'thing/market_scan.html',
        {
            'item_ids': item_ids,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Market orders
@login_required
def orders(request):
    # Retrieve order aggregate data
    cursor = connection.cursor()
    cursor.execute(queries.order_aggregation, (request.user.id,))
    char_orders = OrderedDict()
    for row in dictfetchall(cursor):
        row['slots'] = 5
        char_orders[row['character_id']] = row

    # Retrieve trade skills that we're interested in
    order_cs = CharacterSkill.objects.filter(character__apikeys__user=request.user, skill__item__name__in=ORDER_SLOT_SKILLS.keys())
    order_cs = order_cs.select_related('character__apikey', 'skill__item')

    #for cs in CharacterSkill.objects.select_related().filter(character__apikey__user=request.user, skill__item__name__in=ORDER_SLOT_SKILLS.keys()):
    for cs in order_cs:
        char_id = cs.character.id
        if char_id not in char_orders:
            continue

        char_orders[char_id]['slots'] += (cs.level * ORDER_SLOT_SKILLS.get(cs.skill.item.name, 0))

    # Calculate free slots
    for row in char_orders.values():
        row['free_slots'] = row['slots'] - row['corp_orders'] - row['personal_orders']

    total_row = {
        'free_slots': sum(row['free_slots'] for row in char_orders.values()),
        'slots': sum(row['slots'] for row in char_orders.values()),
        'personal_orders': sum(row['personal_orders'] for row in char_orders.values()),
        'corp_orders': sum(row['corp_orders'] for row in char_orders.values()),
        'sell_orders': sum(row['sell_orders'] for row in char_orders.values()),
        'total_sells': sum(row['total_sells'] for row in char_orders.values()),
        'buy_orders': sum(row['buy_orders'] for row in char_orders.values()),
        'total_buys': sum(row['total_buys'] for row in char_orders.values()),
        'total_escrow': sum(row['total_escrow'] for row in char_orders.values()),
    }

    # Retrieve all orders
    orders = MarketOrder.objects.select_related('item', 'station', 'character', 'corp_wallet__corporation')
    orders = orders.filter(character__apikeys__user=request.user)
    orders = orders.order_by('station__name', '-buy_order', 'item__name')

    now = datetime.datetime.utcnow()
    for order in orders:
        order.z_remaining = (order.expires - now).total_seconds()

    # Render template
    return render_to_response(
        'thing/orders.html',
        {
            'char_orders': char_orders,
            'orders': orders,
            'total_row': total_row,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Trade volume overview
MONTHS = (None, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
@login_required
def trade(request):
    data = {}
    now = datetime.datetime.now()
    
    # Order information
    #orders = Order.objects.filter(corporation=corporation)
    #buy_orders = orders.filter(o_type='B')
    #sell_orders = orders.filter(o_type='S')
    #data['sell_total'] = orders.filter(o_type='S').aggregate(Sum('total_price'))['total_price__sum'] or 0
    #buy_orders = orders.filter(o_type='B')
    #data['buy_total'] = buy_orders.aggregate(Sum('total_price'))['total_price__sum'] or 0
    #data['escrow_total'] = buy_orders.aggregate(Sum('escrow'))['escrow__sum'] or 0
    #data['net_asset_value'] = data['wallet_balance'] + data['sell_total'] + data['escrow_total']
    
    # Transaction stuff oh god
    characters = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    transactions = Transaction.objects.filter(character_id__in=characters)
    
    t_check = []
    # All
    t_check.append(('[All]', 'all', transactions))
    
    # Campaigns
    for camp in Campaign.objects.filter(user=request.user.id):
        title = '[%s]' % (camp.title)
        t_check.append((title, camp.slug, camp.get_transactions_filter(transactions)))

    # Months
    agg = transactions.aggregate(min_date=Min('date'), max_date=Max('date'))
    if agg['min_date'] is not None:
        for year, month in reversed(months_in_range(agg['min_date'], agg['max_date'])):
            name = '%s %s' % (MONTHS[month], year)
            urlpart = '%s-%02d' % (year, month)
            t_check.append((name, urlpart, transactions.filter(date__range=_month_range(year, month))))
    
    # Get data and stuff
    t_data = []
    for name, urlpart, trans in t_check:
        row = dict(
            name=name,
            urlpart=urlpart,
            buy_total=0,
            sell_total=0,
        )
        
        for data in trans.values('buy_transaction').annotate(Sum('total_price')):
            if data['buy_transaction'] is True:
                row['buy_total'] = data['total_price__sum']
            else:
                row['sell_total'] = data['total_price__sum']
        
        row['balance'] = row['sell_total'] - row['buy_total']
        
        t_data.append(row)
    
    data['transactions'] = t_data
    
    # Render template
    return render_to_response(
        'thing/trade.html',
        data,
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Trade overview for a variety of timeframe types
@login_required
def trade_timeframe(request, year=None, month=None, period=None, slug=None):
    # Initialise data
    data = {
        'total_buys': 0,
        'total_sells': 0,
        'total_balance': 0,
        'total_projected_average': 0,
        'total_projected_market': 0,
    }
    
    # Get a QuerySet of transactions by this user
    characters = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    corporations = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))
    wallets = list(CorpWallet.objects.filter(corporation__in=corporations).values_list('account_id', flat=True))
    
    transactions = Transaction.objects.filter(
        Q(character__in=characters) |
        Q(corp_wallet__in=wallets)
    )
    
    # Year/Month
    if year and month:
        year = int(year)
        month = int(month)
        transactions = transactions.filter(date__range=_month_range(year, month))
        data['timeframe'] = '%s %s' % (MONTHS[month], year)
        data['urlpart'] = '%s-%02d' % (year, month)
    # Timeframe slug
    elif slug:
        camp = get_object_or_404(Campaign, slug=slug)
        transactions = camp.get_transactions_filter(transactions)
        data['timeframe'] = '%s (%s -> %s)' % (camp.title, camp.start_date, camp.end_date)
        data['urlpart'] = slug
    # All
    elif period:
        data['timeframe'] = 'all time'
        data['urlpart'] = 'all'
    
    # Fetch the aggregate transaction data
    data_set = transactions.values('buy_transaction', 'item').annotate(
        sum_quantity=Sum('quantity'),
        min_price=Min('price'),
        max_price=Max('price'),
        sum_total=Sum('total_price'),
    )

    t_map = {}
    # { buy_transaction, item, sum_quantity, min_price, max_price, sum_total }
    for row in data_set.iterator():
        item_id = int(row['item'])

        if item_id not in t_map:
            t_map[item_id] = {}

        if row['buy_transaction']:
            t_map[item_id]['buy_quantity'] = row['sum_quantity']
            t_map[item_id]['buy_minimum'] = row['min_price']
            t_map[item_id]['buy_maximum'] = row['max_price']
            t_map[item_id]['buy_total'] = row['sum_total']
            t_map[item_id]['buy_average'] = row['sum_total'] / row['sum_quantity']
        else:
            t_map[item_id]['sell_quantity'] = row['sum_quantity']
            t_map[item_id]['sell_minimum'] = row['min_price']
            t_map[item_id]['sell_maximum'] = row['max_price']
            t_map[item_id]['sell_total'] = row['sum_total']
            t_map[item_id]['sell_average'] = row['sum_total'] / row['sum_quantity']

    # fetch the items
    item_map = Item.objects.select_related().in_bulk(t_map.keys())

    import time
    start = time.time()

    data['items'] = []
    for item in item_map.values():
        t = t_map[item.id]
        item.t = t

        # Average profit
        if 'buy_average' not in t:
            t['buy_average'] = 0
        if 'sell_average' not in t:
            t['sell_average'] = 0

        if t['buy_average'] and t['sell_average']:
            t['average_profit'] = (t['sell_average'] - t['buy_average']).quantize(TWO_PLACES)
            t['average_profit_per'] = '%.1f' % (t['average_profit'] / t['buy_average'] * 100)
        
        if 'buy_quantity' not in t:
            t['buy_quantity'] = 0
        if 'sell_quantity' not in t:
            t['sell_quantity'] = 0

        t['diff'] = t['buy_quantity'] - t['sell_quantity']

        if 'buy_total' not in t:
            t['buy_total'] = 0
        if 'sell_total' not in t:
            t['sell_total'] = 0

        t['balance'] = t['sell_total'] - t['buy_total']

        # Projected balance
        if t['diff'] > 0:
            t['projected_average'] = (t['balance'] + (t['diff'] * t['sell_average'])).quantize(TWO_PLACES)
            t['projected_market'] = (t['balance'] + (t['diff'] * item.sell_price)).quantize(TWO_PLACES)
            t['outstanding'] = ((t['projected_average'] - t['balance']) * -1).quantize(TWO_PLACES)
            if t['outstanding'] == 0:
                t['outstanding'] = ((t['projected_market'] - t['balance']) * -1).quantize(TWO_PLACES)
        else:
            t['projected_average'] = t['balance']
            t['projected_market'] = t['balance']

        data['items'].append(item)
        
        # Update totals
        data['total_buys'] += t['buy_total']
        data['total_sells'] += t['sell_total']
        data['total_projected_average'] += t['projected_average']
        data['total_projected_market'] += t['projected_market']

    # Render template
    return render_to_response(
        'thing/trade_timeframe.html',
        data,
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Transaction list
@login_required
def transactions(request):
    # Get a QuerySet of transactions IDs by this user
    characters = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    transaction_ids = Transaction.objects.filter(character_id__in=characters)
    transaction_ids = transaction_ids.order_by('-date')

    # Get only the ids, at this point joining the rest is unnecessary
    transaction_ids = transaction_ids.values_list('pk', flat=True)

    # Create a new paginator
    paginator = Paginator(transaction_ids, 100)

    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        paginated = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        # Page is not an integer, use first page
        paginated = paginator.page(1)
    except EmptyPage:
        # Page is out of range, deliver last page
        paginated = paginator.page(paginator.num_pages)

    # Actually execute the query to avoid a nested subquery
    paginated_ids = list(paginated.object_list.all())
    transactions = Transaction.objects.filter(pk__in=paginated_ids).select_related('corp_wallet__corporation', 'item', 'station', 'character', 'other_char', 'other_corp')
    transactions = transactions.order_by('-date')

    # Do page number things
    hp = paginated.has_previous()
    hn = paginated.has_next()
    prev = []
    next = []

    if hp:
        # prev and next, use 1 of each
        if hn:
            prev.append(paginated.previous_page_number())
            next.append(paginated.next_page_number())
        # no next, add up to 2 previous links
        else:
            for i in range(paginated.number - 1, 0, -1)[:2]:
                prev.append(i)
    else:
        # no prev, add up to 2 next links
        for i in range(paginated.number + 1, paginator.num_pages)[:2]:
            next.append(i)

    # Render template
    return render_to_response(
        'thing/transactions.html',
        {
            'transactions': transactions,
            'paginated': paginated,
            'next': next,
            'prev': prev,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Transaction details for last x days for specific item
@login_required
def transactions_item(request, item_id, year=None, month=None, period=None, slug=None):
    data = {}
    
    # Get a QuerySet of transactions by this user
    transactions = Transaction.objects.filter(character__apikeys__user=request.user).order_by('-date')
    
    # If item_id is an integer we should filter on that item_id
    if item_id.isdigit():
        transactions = transactions.filter(item=item_id)
        data['item'] = Item.objects.get(pk=item_id).name
    else:
        data['item'] = 'all items'
    
    # Year/Month
    if year and month:
        month = int(month)
        transactions = transactions.filter(date__year=year, date__month=month)
        data['timeframe'] = '%s %s' % (MONTHS[month], year)
    # Timeframe slug
    elif slug:
        camp = get_object_or_404(Campaign, slug=slug)
        transactions = camp.get_transactions_filter(transactions)
        data['timeframe'] = '%s (%s -> %s)' % (camp.title, camp.start_date, camp.end_date)
    # All
    else:
        data['timeframe'] = 'all time'
    
    # Create a new paginator
    paginator = Paginator(transactions.select_related('item', 'station', 'character', 'corp_wallet__corporation', 'other_char', 'other_corp'), 100)
    
    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        transactions = paginator.page(page)
    except (EmptyPage, InvalidPage):
        transactions = paginator.page(paginator.num_pages)
    
    data['transactions'] = transactions
    
    # Render template
    return render_to_response(
        'thing/transactions_item.html',
        data,
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Wallet journal
@login_required
def wallet_journal(request):
    character_ids = list(Character.objects.filter(apikeys__user=request.user.id).values_list('id', flat=True))
    corporation_ids = list(APIKey.objects.filter(user=request.user).exclude(corp_character=None).values_list('corp_character__corporation__id', flat=True))

    journal_ids = JournalEntry.objects.filter(
        (
            Q(character__in=character_ids)
            &
            Q(corp_wallet__isnull=True)
        )
        |
        Q(corp_wallet__corporation__in=corporation_ids)
    )

    # Get only the ids, at this point joining the rest is unnecessary
    journal_ids = journal_ids.values_list('pk', flat=True)

    # Create a new paginator
    paginator = Paginator(journal_ids, 100)

    # Make sure page request is an int, default to 1st page
    try:
        page = int(request.GET.get('page', '1'))
    except ValueError:
        page = 1
    
    # If page request is out of range, deliver last page of results
    try:
        paginated = paginator.page(request.GET.get('page'))
    except PageNotAnInteger:
        # Page is not an integer, use first page
        paginated = paginator.page(1)
    except EmptyPage:
        # Page is out of range, deliver last page
        paginated = paginator.page(paginator.num_pages)

    # Actually execute the query to avoid a nested subquery
    paginated_ids = list(paginated.object_list.all())
    entries = JournalEntry.objects.filter(pk__in=paginated_ids).select_related('character', 'corp_wallet__corporation')
    
    # Do page number things
    hp = paginated.has_previous()
    hn = paginated.has_next()
    prev = []
    next = []

    if hp:
        # prev and next, use 1 of each
        if hn:
            prev.append(paginated.previous_page_number())
            next.append(paginated.next_page_number())
        # no next, add up to 2 previous links
        else:
            for i in range(paginated.number - 1, 0, -1)[:2]:
                prev.append(i)
    else:
        # no prev, add up to 2 next links
        for i in range(paginated.number + 1, paginator.num_pages)[:2]:
            next.append(i)

    # Do some stuff with entries
    item_ids = set()
    owner_ids = set()
    reftype_ids = set()
    station_ids = set()

    for entry in entries:
        owner_ids.add(entry.owner1_id)
        owner_ids.add(entry.owner2_id)
        reftype_ids.add(entry.ref_type_id)

        # Insurance
        if entry.ref_type_id == 19:
            item_ids.add(int(entry.arg_name))
        # Clone Transfer
        elif entry.ref_type_id == 52:
            station_ids.add(int(entry.arg_id))

    char_map = SimpleCharacter.objects.in_bulk(owner_ids)
    corp_map = Corporation.objects.in_bulk(owner_ids)
    alliance_map = Alliance.objects.in_bulk(owner_ids)
    item_map = Item.objects.in_bulk(item_ids)
    rt_map = RefType.objects.in_bulk(reftype_ids)
    station_map = Station.objects.in_bulk(station_ids)

    for entry in entries:
        # Owner 1
        if entry.owner1_id in character_ids:
            entry.z_owner1_mine = True
        entry.z_owner1_char = char_map.get(entry.owner1_id)
        entry.z_owner1_corp = corp_map.get(entry.owner1_id)
        entry.z_owner1_alliance = alliance_map.get(entry.owner1_id)

        # Owner 2
        if entry.owner2_id in character_ids:
            entry.z_owner2_mine = True
        entry.z_owner2_char = char_map.get(entry.owner2_id)
        entry.z_owner2_corp = corp_map.get(entry.owner2_id)
        entry.z_owner2_alliance = alliance_map.get(entry.owner2_id)

        # RefType
        entry.z_reftype = rt_map.get(entry.ref_type_id)

        # Insurance, arg_name is the Item id fo the ship that exploded
        if entry.ref_type_id == 19:
            item = item_map.get(int(entry.arg_name))
            if item:
                entry.z_arg = item.name
        # Clone Transfer, arg_name is the name of the station you're going to
        elif entry.ref_type_id == 52:
            station = station_map.get(entry.arg_id)
            if station:
                entry.z_arg = station.short_name


    # Render template
    return render_to_response(
        'thing/wallet_journal.html',
        {
            'entries': entries,
            'paginated': paginated,
            'next': next,
            'prev': prev,
        },
        context_instance=RequestContext(request)
    )

# ---------------------------------------------------------------------------
# Get a range of days for a year/month eg (01, 31)
def _month_range(year, month):
    start = datetime.datetime(year, month, 1)
    end = datetime.datetime(year, month, calendar.monthrange(year, month)[1], 23, 59, 59)
    return (start, end)

# Fetch all rows from a cursor as a list of dictionaries
def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

def months_in_range(min_date, max_date):
    months = []
    for year in range(min_date.year, max_date.year + 1):
        for month in range(1, 13):
            if year == min_date.year and month < min_date.month:
                continue
            elif year == max_date.year and month > max_date.month:
                continue
            else:
                months.append((year, month))

    return months
