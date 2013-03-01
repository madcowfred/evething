import datetime

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Max, Min, Sum

from thing.models import *
from thing.stuff import *
from thing.templatetags.thing_extras import commas, duration, shortduration

# ---------------------------------------------------------------------------

ONE_DAY = 24 * 60 * 60
EXPIRE_WARNING = 10 * ONE_DAY

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

    # Make a set of characters to hide
    hide_characters = set(int(c) for c in profile.home_hide_characters.split(',') if c)

    # Initialise various data structures
    now = datetime.datetime.utcnow()
    total_balance = 0

    api_keys = set()
    training = set()
    chars = {}
    ship_item_ids = set()
    
    # Try retrieving characters from cache
    cache_key = 'home:characters:%d' % (request.user.id)
    characters = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if characters is None:
        characters = Character.objects.filter(apikeys__user=request.user, apikeys__key_type__in=(APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE))
        characters = characters.prefetch_related('apikeys')
        characters = characters.select_related('config', 'details')
        characters = characters.annotate(total_sp=Sum('characterskill__points'))
        characters = characters.distinct()
        characters = [c for c in characters if c.details is not None]
        cache.set(cache_key, characters, 300)

    for character in characters:
        char_keys = [ak for ak in character.apikeys.all() if ak.user_id == request.user.id]
        api_keys.update(char_keys)

        chars[character.id] = character
        character.z_apikey = char_keys[0]
        character.z_training = {}

        total_balance += character.details.wallet_balance
        if character.details.ship_item_id is not None:
            ship_item_ids.add(character.details.ship_item_id)

    tt.add_time('characters')

    # Try retrieving ship map from cache
    cache_key = 'home:ship_map:%d' % (request.user.id)
    ship_map = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if ship_map is None:
        ship_map = Item.objects.in_bulk(ship_item_ids)
        cache.set(cache_key, ship_map, 300)

    tt.add_time('ship_items')

    # Do skill training check - this can't be in the model because it
    # scales like crap doing individual queries
    skill_qs = []

    queues = SkillQueue.objects.filter(character__in=chars, end_time__gte=now)
    queues = queues.select_related('character__details', 'skill__item')
    for sq in queues:
        char = chars[sq.character_id]
        if 'sq' not in char.z_training:
            char.z_training['sq'] = sq
            char.z_training['skill_duration'] = total_seconds(sq.end_time - now)
            # if char.details:
            char.z_training['sp_per_hour'] = int(sq.skill.get_sp_per_minute(char) * 60)
            char.z_training['complete_per'] = sq.get_complete_percentage(now)
            training.add(char.z_apikey)

            skill_qs.append(Q(character=char, skill=sq.skill))
        
        char.z_training['queue_duration'] = total_seconds(sq.end_time - now)

    tt.add_time('training')

    # Retrieve training skill information
    if skill_qs:
        for cs in CharacterSkill.objects.filter(reduce(q_reduce_or, skill_qs)):
            chars[cs.character_id].z_tskill = cs

    tt.add_time('training skills')

    # Do total skill point aggregation
    total_sp = 0
    for char in characters:
        char.z_total_sp = char.total_sp
        if 'sq' in char.z_training and hasattr(char, 'z_tskill'):
            char.z_total_sp += int(char.z_training['sq'].get_completed_sp(char.z_tskill, now))

        total_sp += char.z_total_sp

    tt.add_time('total_sp')

    # Work out who is and isn't training
    not_training = api_keys - training

    # Do notifications
    for char_id, char in chars.items():
        char.z_notifications = []

        # Game time warnings
        if char.z_apikey.paid_until:
            timediff = total_seconds(char.z_apikey.paid_until - now)

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

        # API key warnings
        if char.z_apikey.expires:
            timediff = total_seconds(char.z_apikey.expires - now)
            if timediff < EXPIRE_WARNING:
                char.z_notifications.append({
                    'icon': 'api-warning',
                    'text': shortduration(timediff),
                    'tooltip': 'API key is close to expiring!',
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
            pri_bonus = getattr(char.details, pri_attrs[1])
            sec_bonus = getattr(char.details, sec_attrs[1])

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
        if hasattr(char, 'z_total_sp') and char.z_total_sp > char.details.clone_skill_points:
            char.z_notifications.append({
                'icon': 'inadequate-clone',
                'text': '%s SP' % (commas(char.details.clone_skill_points)),
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
        temp = [(c.details and c.details.wallet_balance, c.name.lower(), c) for c in char_list]

    temp.sort()
    if profile.home_sort_descending:
        temp.reverse()

    char_list = [s[-1] for s in temp]
    
    tt.add_time('sort')

    # Make separate lists of training and not training characters
    first = [char for char in char_list if char.z_training and char.id not in hide_characters]
    last = [char for char in char_list if not char.z_training and char.id not in hide_characters]

    tt.add_time('training')

    # Try retrieving corporations from cache
    cache_key = 'home:corporations:%d' % (request.user.id)
    corporations = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if corporations is None:
        corp_ids = APIKey.objects.filter(user=request.user.id).exclude(corp_character=None).values('corp_character__corporation')
        corp_map = OrderedDict()
        for corp_wallet in CorpWallet.objects.select_related().filter(corporation__in=corp_ids):
            if corp_wallet.corporation_id not in corp_map:
                corp_map[corp_wallet.corporation_id] = corp_wallet.corporation
                corp_map[corp_wallet.corporation_id].wallets = []
            
            corp_map[corp_wallet.corporation_id].wallets.append(corp_wallet)

        corporations = corp_map.values()
        cache.set(cache_key, corporations, 300)

    tt.add_time('corps')

    # Get old event stats for staff users
    if request.user.is_staff:
        task_count = TaskState.objects.filter(state=TaskState.QUEUED_STATE).aggregate(Count('id'))['id__count']
    else:
        task_count = 0

    tt.add_time('misc junk')

    out = render_page(
        'thing/home.html',
        {
            'profile': profile,
            'not_training': not_training,
            'total_balance': total_balance,
            'total_sp': total_sp,
            'corporations': corporations,
            'characters': first + last,
            'events': list(Event.objects.filter(user=request.user)[:10]),
            'ship_map': ship_map,
            'task_count': task_count,
        },
        request,
        chars.keys(),
        [c.id for c in corporations]
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out
