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

import time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from core.util import json_response
from thing.models import *
from thing.stuff import render_page, flush_cache

# ------------------------------------------------------------------------------

@login_required
def mail(request):
    char_qs = Character.objects.filter(
        apikeys__user=request.user,
    ).distinct()

    characters = []
    for char in char_qs:
        characters.append([
            char.id,
            char.name.replace("'", '&apos;'),
        ])

    return render_page(
        'thing/mail.html',
        dict(
            characters=characters,
        ),
        request,
        [c[0] for c in characters],
    )

# ------------------------------------------------------------------------------

@login_required
def mail_json_body(request, message_id):
    messages = MailMessage.objects.filter(
        message_id=message_id,
        character__apikeys__user=request.user,
    )
    if messages.count() > 0:
        data = dict(body=messages[0].stripped_body())
        messages.update(read=True)
        flush_cache(request.user)
    else:
        data = dict(error='Message does not exist.')

    return json_response(data)

# ------------------------------------------------------------------------------

@login_required
def mail_json_headers(request):
    data = dict(
        characters={},
        alliances={},
        corporations={},
        mailing_lists={},
        messages=[],
    )

    # Build a queryset
    message_qs = MailMessage.objects.filter(
        character__apikeys__user=request.user,
    ).prefetch_related(
        'character',
        'to_characters',
    ).order_by(
        '-sent_date',
    )

    # Collect various IDs
    character_ids = set()
    corp_alliance_ids = set()
    mailing_list_ids = set()
    for message in message_qs:
        character_ids.add(message.sender_id)
        if message.to_corp_or_alliance_id:
            corp_alliance_ids.add(message.to_corp_or_alliance_id)
        if message.to_list_id:
            mailing_list_ids.add(message.to_list_id)

    # Bulk query things
    char_map = Character.objects.in_bulk(character_ids)
    corp_map = Corporation.objects.in_bulk(corp_alliance_ids)
    alliance_map = Alliance.objects.in_bulk(corp_alliance_ids)
    mailing_list_map = MailingList.objects.in_bulk(mailing_list_ids)

    # Mangle data for JSON
    for char in char_map.values():
        data['characters'][char.id] = char.name.replace("'", '&apos;')
    for corp in corp_map.values():
        data['corporations'][corp.id] = dict(
            name=corp.name.replace("'", '&apos;'),
            ticker=corp.ticker,
        )
    for alliance in alliance_map.values():
        data['alliances'][alliance.id] = dict(
            name=alliance.name.replace("'", '&apos;'),
            short_name=alliance.short_name,
        )
    for mailing_list in mailing_list_map.values():
        data['mailing_lists'][mailing_list.id] = mailing_list.name.replace("'", '&apos;')

    # Gather message data
    seen_messages = {}
    for message in message_qs:
        # Skip already seen messages
        m = seen_messages.get(message.message_id)
        if m is not None:
            # Set the message as unread if one version of it is unread
            if message.read == False:
                m['read'] = False

            # Add this character to the to_characters list if it's not already there
            if message.character_id not in m['to_characters']:
                m['to_characters'].append(message.character_id)

            continue

        # Create a new message dict
        m = dict(
            character_id=message.character_id,
            message_id=message.message_id,
            sender_id=message.sender_id,
            # don't need seconds since we don't appear to get them from the API
            sent_date=message.sent_date.strftime('%Y-%m-%d %H:%M'),
            title=message.title,
            to_corp_or_alliance_id=message.to_corp_or_alliance_id,
            to_characters=[],
            to_list_id=message.to_list_id,
            read=message.read,
        )

        # Add any to_characters
        for char in message.to_characters.all():
            data['characters'][char.id] = char.name
            m['to_characters'].append(char.id)

        # Add the character_id to to_characters if it is empty
        if len(m['to_characters']) == 0:
            m['to_characters'].append(message.character_id)

        data['messages'].append(m)
        seen_messages[message.message_id] = m

    return json_response(data)

# ------------------------------------------------------------------------------

@login_required
def mail_mark_read(request):
    if request.method == 'POST':
        message_ids = []
        for k in request.POST.keys():
            if k.startswith('message_'):
                parts = k.split('_')
                if len(parts) == 2 and parts[1].isdigit():
                    message_ids.append(int(parts[1]))

        if message_ids:
            MailMessage.objects.filter(
                character__apikeys__user=request.user,
                message_id__in=message_ids,
            ).update(
                read=True,
            )

            flush_cache(request.user)

    return HttpResponse()

# ------------------------------------------------------------------------------
