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
	elif value >= THOUSAND or value <= -THOUSAND:
		v = Decimal(value) / THOUSAND
		return '%sK' % (v.quantize(Decimal('.1'), rounding=ROUND_UP))
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
