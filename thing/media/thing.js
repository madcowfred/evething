$.tablesorter.addParser({
    id: 'human',
    is: function (s) {
        return (/^[0-9.]+[KMB]?$/).test(s);
    },
    format: function (s) {
        var l = s.length - 1,
            c = s.charAt(l);
        if (c == 'K') {
            return s.substr(0, l) * 1000;
        } else if (c == 'M') {
            return s.substr(0, l) * 1000000;
        } else if (c == 'B') {
            return s.substr(0, l) * 1000000000;
        }

        return s;
    },
    type: 'numeric'
});
