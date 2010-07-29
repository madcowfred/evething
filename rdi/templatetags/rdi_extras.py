import re
from decimal import *

from django import template
from django.template.defaultfilters import stringfilter

re_digits_nondigits = re.compile(r'\d+|\D+')

register = template.Library()


# Put commas in things
# http://code.activestate.com/recipes/498181-add-thousands-separator-commas-to-formatted-number/
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
	if value >= BILLION or value <= -BILLION:
		v = Decimal(value) / BILLION
		return '%sB' % (v.quantize(Decimal('.01'), rounding=ROUND_UP))
	elif value >= MILLION or value <= -MILLION:
		v = Decimal(value) / MILLION
		return '%sM' % (v.quantize(Decimal('.01'), rounding=ROUND_UP))
	elif value >= THOUSAND or value <= -THOUSAND:
		v = Decimal(value) / THOUSAND
		return '%sK' % (v.quantize(Decimal('.1'), rounding=ROUND_UP))
	else:
		return value
