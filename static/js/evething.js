// PHP default? wtf
jQuery.ajaxSettings.traditional = true;


var EVEthing = {
    util: {
        // Get a list of keys in obj sorted by key
        sorted_keys: function(obj) {
            var keys = [];
            for (var key in obj)
                keys.push(key);
            return keys.sort();
        },

        // Get a list of keys in obj sorted by value
        sorted_keys_by_value: function(obj) {
            var keys = [];
            for (var key in obj)
                keys.push(key);
            return keys.sort(function (a,b) {
                if (obj[a] < obj[b]) return -1;
                if (obj[a] > obj[b]) return 1;
                return 0;
            });
        },
    },

    misc: {
        setClock: function() {
            // set up the clock
            var time = new Date();
            var h = time.getUTCHours();
            if (h < 10)
                h = "0" + h;
            var m = time.getUTCMinutes();
            if (m < 10)
                m = "0" + m;
            $('#utc-time').text(h + ":" + m);
        },

        // Enable linking directly to a tab with a #location
        setup_tab_hash: function() {
            // Show the correct tab
            var prefix = 'tab_';
            var hash = document.location.hash;
            if (hash) {
                $('.nav-tabs a[href=' + hash.replace('#', '#' + prefix) + ']').tab('show');
            }

            // Change window hash for page reload
            $('a[data-toggle="tab"]').on('shown', function (e) {
                window.location.hash = e.target.hash.replace('#' + prefix, '#');
            });
        },
    },
}

// Global ready function
$(document).ready(function() {
    // highlight currently active link
    var path = window.location.pathname;
    $('#nav-list li a').each(function() {
        if ($(this).attr('href') == path) {
            $(this).parent().addClass('active');
        }
    });

    // activate bootstrap tooltips
    $('[rel=tooltip]').tooltip();

    // activate bootstrap dropdowns
    $('.dropdown-toggle').dropdown();

    // hover thing for hover things
    $('.skill-hover').popover({ animation: false, trigger: 'hover', html: true });

    EVEthing.misc.setClock();
    window.setInterval(EVEthing.misc.setClock, 5000);
});

// Add our 'human' parser to deal with K/M/B suffixes
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

// Update the tablesorter theme with some bits
$.extend($.tablesorter.themes.bootstrap, {
    icons      : '', // add "icon-white" to make them white; this icon class is added to the <i> in the header
    sortNone   : 'icon-sort',
    sortAsc    : 'icon-caret-up',
    sortDesc   : 'icon-caret-down',
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


// http://codereview.stackexchange.com/a/10396
function parseQueryString() {
    var query = (window.location.search || '?').substr(1),
        map   = {};
    query.replace(/([^&=]+)=?([^&]*)(?:&+|$)/g, function(match, key, value) {
        (map[key] = map[key] || []).push(value.replace(/\+/g, ' '));
    });
    return map;
}

// Handlebars needs a getTemplate function
// http://berzniz.com/post/24743062344/handling-handlebars-js-like-a-pro
Handlebars.getTemplate = function(name) {
    if (Handlebars.templates === undefined || Handlebars.templates[name] === undefined) {
        $.ajax({
            url : '/static/handlebars/' + name + '.handlebars',
            success : function(data) {
                if (Handlebars.templates === undefined) {
                    Handlebars.templates = {};
                }
                Handlebars.templates[name] = Handlebars.compile(data);
            },
            async : false
        });
    }
    return Handlebars.templates[name];
};
