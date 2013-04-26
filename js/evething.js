// PHP default? wtf
jQuery.ajaxSettings.traditional = true;


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


// http://codereview.stackexchange.com/a/10396
function parseQueryString() {
    var query = (window.location.search || '?').substr(1),
        map   = {};
    query.replace(/([^&=]+)=?([^&]*)(?:&+|$)/g, function(match, key, value) {
        (map[key] = map[key] || []).push(value);
    });
    return map;
}


function sorted_keys(obj) {
    var keys = [];
    for (var key in obj)
        keys.push(key);
    return keys.sort(function (a,b) {
        if (obj[a] < obj[b]) return -1;
        if (obj[a] > obj[b]) return 1;
        return 0;
    });
}


var filter_comps = { 'eq': '==', 'ne': '!=', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<=', 'in': 'contains' }

function filter_build(expected, data, ft, fc, fv) {
    var html = '<div class="control-group" style="margin: 0;">';
    html += '<i class="icon-trash"></i> ';
    html += '<select name="ft" class="filter-type input-medium">';
    html += '<option value=""></option>';

    $.each(sorted_keys(expected), function(i, k) {
        if (k === ft)
            html += '<option value="' + k + '" selected>' + expected[k].label + '</option>';
        else
            html += '<option value="' + k + '">' + expected[k].label + '</option>';
    });
    html += '</select>';

    if (ft) {
        html += filter_build_comp(expected, ft, fc);
        html += filter_build_value(data, ft, fc, fv);
    }

    html += '</div>';

    return html;
}

function filter_build_comp(expected, ft, fc) {
    html = ' <select name="fc" class="input-small">';

    for (var k in expected[ft].comps) {
        var v = expected[ft].comps[k];
        if (v == fc)
            html += '<option value="' + v + '" selected>' + filter_comps[v] + '</option>';
        else
            html += '<option value="' + v + '">' + filter_comps[v] + '</option>';
    }

    html += '</select>';
    return html;
}

function filter_build_value(data, ft, fc, fv) {
    html = ' ';

    if (data[ft]) {
        html += '<select name="fv" class="filter-value input-xlarge">';

        $.each(sorted_keys(data[ft]), function(i, d_id) {
            var d_name = data[ft][d_id];
            if (d_id == fv)
                html += '<option value="' + d_id + '" selected>' + d_name + '</option>';
            else
                html += '<option value="' + d_id + '">' + d_name + '</option>';
        });

        html += '</select>';
    }
    else {
        html += '<input name="fv" class="filter-value input-xlarge" type="text" value="' + fv + '">';
    }

    return html;
}

function bind_aggregate_button() {
    $('#aggregate-form').submit(function() {
        var action = $(this).attr('action');
        var data = $('#filter-form, #aggregate-form').serialize();
        window.location.href = action + '?' + data;
        return false;
    });
}
