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

from .apitask import APITask

from thing.models.mailmessage import MailMessage

# ------------------------------------------------------------------------------

class MailBodies(APITask):
    name = 'thing.mail_bodies'
    url = '/char/MailBodies.xml.aspx'

    def run(self, apikey_id, character_id, ids):
        if self.init(apikey_id=apikey_id) is False:
            return

        # Set up our queryset
        m_filter = MailMessage.objects.filter(
            character=character_id,
        )

        params = dict(
            characterID=character_id,
            ids=ids,
        )
        if self.fetch_api(MailBodies.url, params) is False or self.root is None:
            return

        # New list of mail IDs
        mail_bodies = {}
        for row in self.root.findall('result/rowset/row'):
            text = row.text
            if text is None:
                text = ''

            mail_bodies[int(row.attrib['messageID'])] = text.replace('<br>', '\n')

        # Bulk fetch mail from database and update any new body fields
        for mm in m_filter.filter(message_id__in=mail_bodies.keys()):
            if mm.body != mail_bodies[mm.message_id]:
                mm.body = mail_bodies[mm.message_id]
                mm.save(update_fields=('body',))

        return True

# ------------------------------------------------------------------------------
