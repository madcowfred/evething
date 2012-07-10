import re
from decimal import *

from django import template
from django.template.defaultfilters import stringfilter
from django.utils.safestring import mark_safe

register = template.Library()

# Put commas in things
# http://code.activestate.com/recipes/498181-add-thousands-separator-commas-to-formatted-number/
re_digits_nondigits = re.compile(r'\d+|\D+')

@register.filter
@stringfilter
def commas(value):
    parts = re_digits_nondigits.findall(value)
    for i in xrange(len(parts)):
        s = parts[i]
        if s.isdigit():
            parts[i] = _commafy(s)
            break
    return ''.join(parts)

def _commafy(s):
    r = []
    for i, c in enumerate(reversed(s)):
        if i and (not (i % 3)):
            r.insert(0, ',')
        r.insert(0, c)
    return ''.join(r)


# Shorten numbers to a human readable version
THOUSAND = 10**3
TEN_THOUSAND = 10**4
MILLION = 10**6
BILLION = 10**9
@register.filter
def humanize(value):
    if value is None or value == '':
        return '0'
    
    if value >= BILLION or value <= -BILLION:
        v = Decimal(value) / BILLION
        return '%sB' % (v.quantize(Decimal('.01'), rounding=ROUND_UP))
    elif value >= MILLION or value <= -MILLION:
        v = Decimal(value) / MILLION
        if v >= 10:
            return '%sM' % (v.quantize(Decimal('.1'), rounding=ROUND_UP))
        else:
            return '%sM' % (v.quantize(Decimal('.01'), rounding=ROUND_UP))
    elif value >= TEN_THOUSAND or value <= -TEN_THOUSAND:
        v = Decimal(value) / THOUSAND
        return '%sK' % (v.quantize(Decimal('.1'), rounding=ROUND_UP))
    elif value >= THOUSAND or value <= -THOUSAND:
        return '%s' % (commas(Decimal(value).quantize(Decimal('1.'), rounding=ROUND_UP)))
    else:
        if isinstance(value, Decimal):
            return value.quantize(Decimal('.1'), rounding=ROUND_UP)
        else:
            return value


# Turn a duration in seconds into a human readable string
@register.filter
def duration(s):
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    
    parts = []
    if d:
        parts.append('%dd' % (d))
    if h:
        parts.append('%dh' % (h))
    if m:
        parts.append('%dm' % (m))
    if s:
        parts.append('%ds' % (s))
    
    return ' '.join(parts)

# Turn a duration in seconds into a shorter human readable string
@register.filter
def shortduration(s):
    return ' '.join(duration(s).split()[:2])

# Do balance colouring (red for negative, green for positive)
@register.filter
@stringfilter
def balance(s):
    if s == '0':
        return s
    elif s.startswith('-'):
        return mark_safe('<span class="neg">%s</span>' % (s))
    else:
        return mark_safe('<span class="pos">%s</span>' % (s))

# Conditionally wrap some text in a span if it matches a condition. Ugh.
@register.filter
def spanif(value, arg):
    parts = arg.split()
    if len(parts) != 3:
        return value
    
    n = int(parts[2])
    if (parts[1] == '<' and value < n) or (parts[1] == '=' and value == n) or (parts[1] == '>' and value > n):
        return mark_safe('<span class="%s">%s</span>' % (parts[0], value))
    else:
        return value


@register.filter
def tablecols(data, cols):
    rows = []
    row = []
    index = 0
    for user in data:
        row.append(user)
        index = index + 1
        if index % cols == 0:
            rows.append(row)
            row = []
    # Still stuff missing?
    if len(row) > 0:
        for i in range(cols - len(row)):
            row.append([])
        rows.append(row)
    return rows


# look up value key in dictionary d
@register.filter
def dictlookup(d, key):
    return d[key]


# Modulus
@register.filter
def modulus(v, d):
    return v % d
