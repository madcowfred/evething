import re

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
#from django.db.models import Q, Avg, Count, Max, Min, Sum
from django.shortcuts import redirect, get_object_or_404
from django.template import RequestContext

from coffin.shortcuts import *

from thing.models import *
from thing.stuff import TimerThing, total_seconds

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
    
    utcnow = datetime.datetime.utcnow()

    # Do various visibility things here instead of in awful template code
    show = {
        'clone': not anonymous and (not public or char.config.show_clone),
        'implants': not anonymous and (not public or char.config.show_implants),
        'queue': anonymous or not public or char.config.show_skill_queue,
        'standings': not anonymous and (not public or char.config.show_standings),
        'wallet': not anonymous and (not public or char.config.show_wallet),
    }

    # Retrieve skill queue
    queue = []
    training_id = None
    training_level = None
    queue_duration = None

    if show['queue']:
        queue = list(SkillQueue.objects.select_related('skill__item', 'character__corporation').filter(character=char, end_time__gte=utcnow).order_by('end_time'))
        if queue:
            training_id = queue[0].skill.item.id
            training_level = queue[0].to_level
            queue_duration = total_seconds(queue[-1].end_time - utcnow)

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
        if show['queue'] and cs.skill.item.id == training_id:
            cs.z_icons.append('partial')
            cs.z_training = True
            cs.z_class = "training-highlight"

            # add partially trained SP to the total
            total_sp += int(queue[0].get_completed_sp(cs, utcnow))

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
                entry.z_remaining = total_seconds(training_skill.end_time - utcnow)
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
