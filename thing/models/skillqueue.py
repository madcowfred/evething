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

import datetime

from django.db import models

from core.util import total_seconds
from thing.models.character import Character
from thing.models.skill import Skill

# ------------------------------------------------------------------------------
# Skill queue
class SkillQueue(models.Model):
    character = models.ForeignKey(Character)
    skill = models.ForeignKey(Skill)

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    start_sp = models.IntegerField()
    end_sp = models.IntegerField()
    to_level = models.SmallIntegerField()

    class Meta:
        app_label = 'thing'
        ordering = ('start_time',)

    def __unicode__(self):
        return '%s: %s %d, %d -> %d - Start: %s, End: %s' % (self.character.name,
            self.skill.item.name, self.to_level, self.start_sp, self.end_sp,
            self.start_time, self.end_time)

    def get_complete_percentage(self, now=None, character=None):
        if now is None:
            now = datetime.datetime.utcnow()
        remaining = total_seconds(self.end_time - now)
        remain_sp = remaining / 60.0 * self.skill.get_sp_per_minute(character or self.character)
        required_sp = self.skill.get_sp_at_level(self.to_level) - self.skill.get_sp_at_level(self.to_level - 1)

        return round(100 - (remain_sp / required_sp * 100), 1)

    def get_completed_sp(self, charskill, now=None, character=None):
        if now is None:
            now = datetime.datetime.utcnow()

        remaining = total_seconds(self.end_time - now)
        remain_sp = remaining / 60.0 * self.skill.get_sp_per_minute(character or self.character)
        required_sp = self.skill.get_sp_at_level(self.to_level) - self.skill.get_sp_at_level(self.to_level - 1)

        base_sp = self.skill.get_sp_at_level(charskill.level)
        current_sp = charskill.points

        return (required_sp - remain_sp) - (current_sp - base_sp)

    def get_roman_level(self):
        return ['', 'I', 'II', 'III', 'IV', 'V'][self.to_level]

    def get_remaining(self):
        remaining = total_seconds(self.end_time - datetime.datetime.utcnow())
        return int(remaining)

# ------------------------------------------------------------------------------
