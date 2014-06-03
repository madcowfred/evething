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

import random
import re

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404

from core.util import json_response
from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8


def character_sheet(request, character_name):
    """Display a character page"""
    characters = Character.objects.select_related('config', 'details', 'corporation__alliance')
    characters = characters.filter(apikeys__valid=True)
    characters = characters.distinct()

    char = get_object_or_404(characters, name=character_name)
    print char.config
    print char.details

    # Check access
    public = True
    if request.user.is_authenticated() and char.apikeys.filter(user=request.user).count():
        public = False

    # If it's for public access, make sure this character is visible
    if public and not char.config.is_public:
        raise Http404

    return character_common(request, char, public=public)


def character_anonymous(request, anon_key):
    """Display an anonymized character page"""
    char = get_object_or_404(Character.objects.select_related('config', 'details'), config__anon_key=anon_key)

    return character_common(request, char, anonymous=True)


def character_common(request, char, public=True, anonymous=False):
    """Common code for character views"""
    tt = TimerThing('character_common')

    utcnow = datetime.datetime.utcnow()

    # I don't know how this happens but hey, let's fix it here
    if char.config is None:
        char.config = CharacterConfig.objects.create(
            character=char,
        )

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
    # training_level = None
    queue_duration = None

    if show['queue']:
        queue = list(SkillQueue.objects.select_related('skill__item', 'character__corporation', 'character__details').filter(character=char, end_time__gte=utcnow).order_by('end_time'))
        if queue:
            training_id = queue[0].skill.item.id
            # training_level = queue[0].to_level
            queue_duration = total_seconds(queue[-1].end_time - utcnow)
            queue[0].z_complete = queue[0].get_complete_percentage()

    tt.add_time('skill queue')

    # Try retrieving skill data from cache
    cache_key = 'character:skills:%s' % (char.id)
    skill_data = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if skill_data is None:
        # Retrieve the list of skills and group them by market group
        skills = OrderedDict()
        cur = None

        # Fake MarketGroup for unpublished skills
        total_sp = 0

        unpub_mg = MarketGroup(id=0, name="Unpublished")
        unpub_mg.z_total_sp = 0
        skills[unpub_mg] = []

        css = CharacterSkill.objects.filter(character=char)
        css = css.select_related('skill__item__market_group')
        css = css.order_by('skill__item__market_group__name', 'skill__item__name')

        for cs in css:
            mg = cs.skill.item.market_group or unpub_mg
            if mg != cur:
                cur = mg
                cur.z_total_sp = 0
                skills[cur] = []

            cs.z_icons = []
            # level 5 skill = 5 special icons
            if cs.level == 5:
                cs.z_icons.extend(['star level5'] * 5)
                cs.z_class = "level5"
            # 0-4 = n icons
            else:
                cs.z_icons.extend(['star'] * cs.level)

            # training skill can have a training icon
            if show['queue'] and cs.skill.item.id == training_id:
                cs.z_icons.append('star training-highlight')
                cs.z_training = True
                cs.z_class = "training-highlight"

                # add partially trained SP to the total
                total_sp += int(queue[0].get_completed_sp(cs, utcnow))

            # partially trained skills get a partial icon
            elif cs.points > cs.skill.get_sp_at_level(cs.level):
                cs.z_icons.append('star-empty training-highlight')

            # then fill out the rest with empty icons
            cs.z_icons.extend(['star-empty'] * (5 - len(cs.z_icons)))

            skills[cur].append(cs)
            cur.z_total_sp += cs.points
            if cur is not unpub_mg:
                total_sp += cs.points

        # Move the fake MarketGroup to the end if it has any skills
        k, v = skills.popitem(False)
        if v:
            skills[k] = v

        skill_data = (total_sp, skills)
        cache.set(cache_key, skill_data, 300)

    # Data was cached
    else:
        total_sp, skills = skill_data

    tt.add_time('skill group')

    # Retrieve skillplans
    #user_ids = APIKey.objects.filter(characters__name=char.name).values_list('user_id', flat=True)

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

    plans = plans.select_related('user')

    # Sort out the plans and apply icon states
    user_plans = []
    public_plans = []
    for sp in plans:
        if sp.visibility == SkillPlan.PRIVATE_VISIBILITY:
            sp.z_icon = 'lock'
        elif sp.visibility == SkillPlan.PUBLIC_VISIBILITY:
            sp.z_icon = 'eye-open'
        elif sp.visibility == SkillPlan.GLOBAL_VISIBILITY:
            sp.z_icon = 'globe'

        if sp.user_id == request.user.id:
            user_plans.append(sp)
        else:
            public_plans.append(sp)

    tt.add_time('skill plans')

    if show['standings']:
        # Try retrieving standings data from cache
        cache_key = 'character:standings:%s' % (char.id)
        standings_data = cache.get(cache_key)
        # Not cached, fetch from database and cache
        if standings_data is None:
            faction_standings = list(char.factionstanding_set.select_related().all())
            corp_standings = list(char.corporationstanding_set.select_related().all())
            standings_data = (faction_standings, corp_standings)
            cache.set(cache_key, standings_data, 300)
        # Data was cached
        else:
            faction_standings, corp_standings = standings_data
    else:
        faction_standings = []
        corp_standings = []

    # Render template
    out = render_page(
        'thing/character.html',
        {
            'char': char,
            'public': public,
            'anonymous': anonymous,
            'show': show,
            'total_sp': total_sp,
            'skills': skills,
            'queue': queue,
            'queue_duration': queue_duration,
            'user_plans': user_plans,
            'public_plans': public_plans,
            'faction_standings': faction_standings,
            'corp_standings': corp_standings,
        },
        request,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

ANON_KEY_RE = re.compile(r'^[a-z0-9]{16}$')
ANON_KEY_CHOICES = 'abcdefghijklmnopqrstuvwxyz0123456789'


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

    # User wants to enable anonymous key
    if 'anon-key-toggle' in request.POST:
        anon_key = request.POST.get('anon-key', '').lower()
        # Provided key is OK, use that
        if ANON_KEY_RE.match(anon_key):
            char.config.anon_key = anon_key
        # Generate a new key
        else:
            char.config.anon_key = ''.join([random.choice(ANON_KEY_CHOICES) for i in range(16)])
    else:
        char.config.anon_key = ''

    char.config.save()

    return json_response(dict(anon_key=char.config.anon_key))


def character_skillplan(request, character_name, skillplan_id):
    """Display a SkillPlan for a character"""
    public = True

    # If the user is logged in, check if the character belongs to them
    if request.user.is_authenticated():
        try:
            character = Character.objects.select_related('config', 'details').distinct().get(name=character_name, apikeys__user=request.user)
        except Character.DoesNotExist:
            pass
        else:
            public = False
            qs = Q(visibility=SkillPlan.GLOBAL_VISIBILITY) | Q(user=request.user)
            skillplan = get_object_or_404(SkillPlan.objects.prefetch_related('entries'), qs, pk=skillplan_id)

    # Not logged in or character does not belong to user
    if public is True:
        character = get_object_or_404(Character.objects.select_related('config', 'details'), name=character_name, config__is_public=True)

        qs = Q(visibility=SkillPlan.GLOBAL_VISIBILITY)
        if request.user.is_authenticated():
            qs |= Q(user=request.user)
        skillplan = get_object_or_404(SkillPlan.objects.prefetch_related('entries'), qs, pk=skillplan_id)

    return character_skillplan_common(request, character, skillplan, public=public)


def character_anonymous_skillplan(request, anon_key, skillplan_id):
    """Display a SkillPlan for an anonymous character"""
    character = get_object_or_404(Character.objects.select_related('config', 'details'), config__anon_key=anon_key)
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

    # Try retrieving learned data from cache
    cache_key = 'character_skillplan:learned:%s' % (character.id)
    learned = cache.get(cache_key)
    # Not cached, fetch from database and cache
    if learned is None:
        learned = {}
        for cs in CharacterSkill.objects.filter(character=character).select_related('skill__item'):
            learned[cs.skill.item.id] = cs
        cache.set(cache_key, learned, 300)

    tt.add_time('char skills')

    # Possibly get training information
    training_skill = None
    if anonymous is True or public is False or character.config.show_skill_queue is True:
        sqs = list(SkillQueue.objects.select_related('skill__item').filter(character=character, end_time__gte=utcnow))
        if sqs:
            training_skill = sqs[0]

    tt.add_time('training')

    # Initialise stat stuff
    if character.details:
        remap_stats = dict(
            int_attribute=character.details.int_attribute,
            mem_attribute=character.details.mem_attribute,
            per_attribute=character.details.per_attribute,
            wil_attribute=character.details.wil_attribute,
            cha_attribute=character.details.cha_attribute,
        )
    else:
        remap_stats = dict(
            int_attribute=0,
            mem_attribute=0,
            per_attribute=0,
            wil_attribute=0,
            cha_attribute=0,
        )

    implant_stats = {}
    for stat in ('int', 'mem', 'per', 'wil', 'cha'):
        k = '%s_bonus' % (stat)
        if implants == 0 and implants_visible is True:
            implant_stats[k] = getattr(character.details, k, 0)
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
                # check if current skill SP > level SP AND planned skill lvl - 1 = learned skill level
                elif cs.points > cs.skill.get_sp_at_level(cs.level) and entry.sp_skill.level - 1 == cs.level:
                    required_sp = cs.skill.get_sp_at_level(cs.level + 1) - cs.skill.get_sp_at_level(cs.level)
                    sp_done = cs.points - cs.skill.get_sp_at_level(cs.level)
                    entry.z_sp_done = sp_done
                    entry.z_percent_trained = round(sp_done / float(required_sp) * 100, 1)
                    entry.z_partial_trained = True

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
                entry.z_percent_trained = training_skill.get_complete_percentage()
            elif hasattr(entry, 'z_partial_trained'):
                remaining_sp = skill.get_sp_at_level(entry.sp_skill.level) - skill.get_sp_at_level(entry.sp_skill.level - 1)
                entry.z_remaining = (remaining_sp - entry.z_sp_done) / entry.z_sppm * 60
                entry.z_total_time = remaining_sp / entry.z_sppm * 60
            else:
                entry.z_remaining = (skill.get_sp_at_level(entry.sp_skill.level) - skill.get_sp_at_level(entry.sp_skill.level - 1)) / entry.z_sppm * 60

            # Add time remaining to total
            if not hasattr(entry, 'z_trained'):
                total_remaining += entry.z_remaining

        entries.append(entry)

    tt.add_time('skillplan loop')

    out = render_page(
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
        request,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out
