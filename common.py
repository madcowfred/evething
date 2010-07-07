def nice_time(s):
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

def commas(n):
	s = str(n)
	if '.' in s:
		l, r = s.split('.')
	else:
		l = s
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
