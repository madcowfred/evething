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

from django.conf import settings
from django.contrib.auth.decorators import login_required

from thing.models import *  # NOPEP8
from thing.stuff import *  # NOPEP8

EXTRACTORS = [2848, 3060, 3061, 3062, 3063, 3064, 3067, 3068]
LAUNCHPADS = [2544, 2543, 2552, 2555, 2542, 2556, 2557, 2256]
STORAGE = [2541, 2536, 2257, 2558, 2535, 2560, 2561, 2562] + LAUNCHPADS

@login_required
def pi(request):
    """PI"""
    tt = TimerThing('pi')

    characters = Character.objects.filter(
        apikeys__user=request.user,
        apikeys__valid=True,
        apikeys__key_type__in=[APIKey.ACCOUNT_TYPE, APIKey.CHARACTER_TYPE]
    ).distinct().select_related('colony_set')

    pi_map = {}
    for character in characters:
        colonies = character.colony_set.all()
        if colonies is not None and len(colonies):
            char = pi_map.get(character.id, None)
            if char is None:
                char = {
                    'character': character,
                    'colonies': {}
                }
            for colony in colonies:
                char['colonies'][colony.id] = {
                    'colony': colony
                }
                char['colonies'][colony.id]['extractors'] = colony.pin_set.filter(
                    type__in=EXTRACTORS).all()
                char['colonies'][colony.id]['launchpads'] = colony.pin_set.filter(
                    type__in=LAUNCHPADS).all()
                char['colonies'][colony.id]['storage'] = colony.pin_set.filter(
                    type__in=STORAGE).all()

            pi_map[character.id] = char

    tt.add_time('organizing')

    # Render template
    out = render_page(
        'thing/pi.html',
        {
            'map': pi_map
        },
        request,
    )

    tt.add_time('template')
    if settings.DEBUG:
        tt.finished()

    return out

