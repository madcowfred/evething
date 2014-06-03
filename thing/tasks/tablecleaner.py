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

from celery import task
from celery.utils.log import get_task_logger
logger = get_task_logger(__name__)

from django.db.models import Q

from thing.models import APIKey, TaskState


@task(name='thing.table_cleaner')
def table_cleaner():
    """Periodic task to perform database table cleanup"""
    utcnow = datetime.datetime.utcnow()

    queued_timeout = utcnow - datetime.timedelta(hours=12)

    # Build a QuerySet to find broken tasks
    taskstates = TaskState.objects.filter(state=TaskState.QUEUED_STATE, mod_time__lte=queued_timeout)
    for ts in taskstates:
        logger.warn('[table_cleaner] Stuck task: %d | %d | %s | %s', ts.id, ts.keyid, ts.parameter, ts.url)

    count = taskstates.update(mod_time=utcnow, next_time=utcnow, state=TaskState.READY_STATE)
    if count > 0:
        logger.warn('[table_cleaner] Reset %d broken task(s)', count)

    # Build a QuerySet to find tasks that refer to no longer existent keys
    taskstates = TaskState.objects.exclude(
        Q(keyid=-1)
        |
        Q(keyid__in=APIKey.objects.filter(valid=True).values('keyid'))
    )
    taskstates.delete()
