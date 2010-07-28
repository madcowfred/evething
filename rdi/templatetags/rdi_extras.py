import re

from django import template
from django.template.defaultfilters import stringfilter

re_digits_nondigits = re.compile(r'\d+|\D+')

register = template.Library()


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


def oldcommas(value):
	if '.' in value:
		l, r = value.split('.')
	else:
		l = value
		r = ''
	
	rev = l[::-1]
	
	newnum = []
	for i in range(0, len(l), 3):
		newnum.insert(0, rev[i:i+3][::-1])
	
	l = ','.join(newnum)
	if r:
		return '%s.%s' % (l, r)
	else:
		return l
