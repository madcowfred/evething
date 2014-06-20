EVEthing.bpcalc = {
    onload: function () {
        // call the tablesorter plugin
        $("#build-table").tablesorter({
            'headers': {
                1: { sorter: false },
                2: { sorter: 'human' },
                3: { sorter: 'human' },
                4: { sorter: false },
                5: { sorter: 'human' },
                7: { sorter: false },
                8: { sorter: 'human' },
                10: { sorter: false },
                11: { sorter: false },
                12: { sorter: false },
                13: { sorter: false },
                14: { sorter: false },
                15: { sorter: false }
            },
            'sortList': [[8, 1]]
        });
    },

    filter_profit: function () {
        var keep = [],
            min_profit = $('#profit').attr('value');
        $("#build-table tbody tr").each(function (i, tr) {
            var profit_td = $(tr).children()[9],
                profit = parseFloat($(profit_td).text().split('%')[0]);

            if (profit >= min_profit) {
                keep.push('bpi=' + $(tr).attr('data_bpi'));
            }
        });

        var parsed = parseUri(window.location.href);
        var days = parsed.queryKey.days;
        window.location = parsed.path + '?days=' + days + '&' + keep.join('&');
    },

    filter_movement: function () {
        var keep = [],
            max_movement = $('#movement').attr('value');
        $("#build-table tbody tr").each(function (i, tr) {
            var movement_td = $(tr).children()[14],
                movement = parseFloat($(movement_td).text().split('%')[0]);

            if (movement < max_movement) {
                keep.push('bpi=' + $(tr).attr('data_bpi'));
            }
        });

        var parsed = parseUri(window.location.href);
        var days = parsed.queryKey.days;
        window.location = parsed.path + '?days=' + days + '&' + keep.join('&');
    },

    filter_slots: function () {
        var keep = [],
            slots = $('#slots').val();
        $("#build-table tbody tr").each(function (i, tr) {
            if (i < slots) {
                keep.push('bpi=' + $(tr).attr('data_bpi'));
            }
        });

        var parsed = parseUri(window.location.href);
        var days = parsed.queryKey.days;
        window.location = parsed.path + '?days=' + days + '&' + keep.join('&');
    },

    filter_checked: function () {
        var keep = [];
        $('#build-table tbody tr td input').each(function (i, input) {
            if (!input.checked) {
                keep.push('bpi=' + $(input).closest('tr').attr('data_bpi'));
            }
        });

        var parsed = parseUri(window.location.href);
        var days = parsed.queryKey.days;
        window.location = parsed.path + '?days=' + days + '&' + keep.join('&');
    }
};
