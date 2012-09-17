import gzip
import time
from cStringIO import StringIO

try:
    import xml.etree.cElementTree as ET
except:
    import xml.etree.ElementTree as ET

from thing.models import *

# ---------------------------------------------------------------------------
# Times things
class TimerThing:
    def __init__(self, name):
        self.times = []
        self.add_time(name)

    def add_time(self, name):
        self.times.append([time.time(), name])

    def finished(self):
        print 'TimerThing: %s' % (self.times[0][1])
        print '-' * 23
        for i in range(1, len(self.times)):
            t, name = self.times[i]
            print '%-15s: %.3fs' % (name, t - self.times[i-1][0])
        print '-' * 23
        print '%-15s: %.3fs' % ('total', self.times[-1][0] - self.times[0][0])

# ---------------------------------------------------------------------------
# Fetch all rows from a cursor as a list of dictionaries
def dictfetchall(cursor):
    "Returns all rows from a cursor as a dict"
    desc = cursor.description
    return [
        dict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()
    ]

# ---------------------------------------------------------------------------
# Convert a datetime.timedelta object into a number of seconds
def total_seconds(delta):
    return (delta.days * 24 * 60 * 60) + delta.seconds

# ---------------------------------------------------------------------------
