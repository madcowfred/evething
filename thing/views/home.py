import datetime

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *
from thing.stuff import TimerThing, total_seconds, q_reduce_or
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

    for apikey in APIKey.objects.prefetch_related('characters').filter(user=request.user).exclude(key_type=APIKey.CORPORATION_TYPE):
        api_keys.add(apikey)
        for char in apikey.characters.all():
            if char.id not in chars:
                chars[char.id] = char
                char.z_apikey = apikey
                char.z_training = {}
                total_balance += char.wallet_balance
                if char.ship_item_id is not None:
                    ship_item_ids.add(char.ship_item_id)

    tt.add_time('apikeys')

    ship_map = Item.objects.in_bulk(ship_item_ids)

    tt.add_time('ship_items')

    # Do skill training check - this can't be in the model because it
    # scales like crap doing individual queries
    skill_qs = []

    queues = SkillQueue.objects.select_related('character', 'skill__item').filter(character__in=chars, end_time__gte=now)
    for sq in queues:
        char = chars[sq.character_id]
        if 'sq' not in char.z_training:
            char.z_training['sq'] = sq
            char.z_training['skill_duration'] = total_seconds(sq.end_time - now)
            char.z_training['sp_per_hour'] = int(sq.skill.get_sp_per_minute(char) * 60)
            char.z_training['complete_per'] = sq.get_complete_percentage(now)
            training.add(char.z_apikey)

            skill_qs.append(Q(character=char, skill=sq.skill))
        
        char.z_training['queue_duration'] = total_seconds(sq.end_time - now)

    tt.add_time('training')

    # Retrieve training skill information
    for cs in CharacterSkill.objects.filter(reduce(q_reduce_or, skill_qs)):
        chars[cs.character_id].z_tskill = cs

    # Do total skill point aggregation
    total_sp = 0
    for cs in CharacterSkill.objects.select_related().filter(character__in=chars).values('character').annotate(total_sp=Sum('points')):
        char = chars[cs['character']]
        char.z_total_sp = cs['total_sp']

        # Current skill training
        if 'sq' in char.z_training:
            base_sp = char.z_training['sq'].skill.get_sp_at_level(char.z_tskill.level)
            current_sp = char.z_tskill.points
            trained_sp = char.z_training['sq'].get_completed_sp(now)
            extra_sp = trained_sp - (current_sp - base_sp)

            char.z_total_sp += int(extra_sp)

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
            'ship_map': ship_map,
            'task_count': task_count,
        },
        context_instance=RequestContext(request)
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out
