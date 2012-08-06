$(document).ready(function() {
    // highlight currently active link
    var path = window.location.pathname;
    $('#nav-list li a').each(function() {
        if ($(this).attr('href') == path) {
            $(this).parent().addClass('active');
        }
    });

    // activate bootstraptooltips
    $("[rel=tooltip]").tooltip();
    // activate bootstrap dropdowns
    $('.dropdown-toggle').dropdown();

    setClock();
    window.setInterval(setClock, 5000);
});

function setClock() {
    // set up the clock
    var time = new Date();
    var h = time.getUTCHours();
    if (h < 10)
        h = "0" + h;
    var m = time.getUTCMinutes();
    if (m < 10)
        m = "0" + m;
    $('#utc-time').text(h + ":" + m);
}



$.tablesorter.addParser({
    id: 'human',
    is: function(s) {
        return /^[0-9\,\.]+[KMB]?$/.test(s);
    },
    format: function(s) {
        var s = s.replace(/\,/g,'');
        var l = s.length - 1;
        var c = s.charAt(l);
        if (c == 'K') {
            return s.substr(0, l) * 1000;
        }
        else if (c == 'M') {
            return s.substr(0, l) * 1000000;
        }
        else if (c == 'B') {
            return s.substr(0, l) * 1000000000;
        }
        else {
            return s;
        }
    },
    type: 'numeric',
});


function parseUri (str) {
    var    o   = parseUri.options,
        m   = o.parser[o.strictMode ? "strict" : "loose"].exec(str),
        uri = {},
        i   = 14;

    while (i--) uri[o.key[i]] = m[i] || "";

    uri[o.q.name] = {};
    uri[o.key[12]].replace(o.q.parser, function ($0, $1, $2) {
        if ($1) uri[o.q.name][$1] = $2;
    });

    return uri;
};

parseUri.options = {
    strictMode: false,
    key: ["source","protocol","authority","userInfo","user","password","host","port","relative","path","directory","file","query","anchor"],
    q:   {
        name:   "queryKey",
        parser: /(?:^|&)([^&=]*)=?([^&]*)/g
    },
    parser: {
        strict: /^(?:([^:\/?#]+):)?(?:\/\/((?:(([^:@]*)(?::([^:@]*))?)?@)?([^:\/?#]*)(?::(\d*))?))?((((?:[^?#\/]*\/)*)([^?#]*))(?:\?([^#]*))?(?:#(.*))?)/,
        loose:  /^(?:(?![^:@]+:[^:@\/]*@)([^:\/?#.]+):)?(?:\/\/)?((?:(([^:@]*)(?::([^:@]*))?)?@)?([^:\/?#]*)(?::(\d*))?)(((\/(?:[^?#](?![^?#\/]*\.[^?#\/.]+(?:[?#]|$)))*\/?)?([^?#\/]*))(?:\?([^#]*))?(?:#(.*))?)/
    }
};


function randString(n)
{
    var text = '';
    var possible = 'abcdefghijklmnopqrstuvwxyz0123456789';

    for(var i=0; i < n; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }

    return text;
}
