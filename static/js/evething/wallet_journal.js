EVEthing.wallet_journal = {
    onload: function() {
        // Add our provided filters
        var count = 0;
        $.each(EVEthing.wallet_journal.filters, function(ft, fcfvs) {
            for (var i = 0; i < fcfvs.length; i++) {
                $('#filters').append(EVEthing.filters.build(ft, fcfvs[i][0], fcfvs[i][1]));
                count++;
            }
        });
        // If we didn't add any filters, make an empty one
        if (count === 0) {
            $('#filters').append(EVEthing.filters.build());
        }

        // add query string to pagination links
        var search = document.location.search;
        $('a').each(function() {
            var href = $(this).attr('href');
            if (href !== undefined && href.substr(0, 5) === '?page') {
                var params = parseQueryString();
                params.page = href.split(/=/)[1];
                //console.log(params);
                $(this).attr('href', '?' + $.param(params));
            }
        });

        // bind filter events
        EVEthing.filters.bind_events();

        // bind aggregate button
        $('#aggregate-form').submit(function() {
            var action = $(this).attr('action');
            var data = $('#filter-form, #aggregate-form').serialize();
            window.location.href = action + '?' + data;
            return false;
        });
    },
}
