EVEthing.wallet_journal = {
    onload: function () {
        // Add query string to pagination links
        $('a').each(function () {
            var href = $(this).attr('href');
            if (href !== undefined && href.substr(0, 5) === '?page') {
                var params = parseQueryString();
                params.page = href.split(/=/)[1];
                $(this).attr('href', '?' + $.param(params));
            }
        });
        
        // Add query string to export link
        $('a#export-button').each(function() {
            var href = $(this).attr('href').split('?', 1)[0];
            var param = $.param(parseQueryString())
            if (param !== '') {
                $(this).attr('href', href + '?' + param);
            }
        });  
        
        // Bind filter events
        EVEthing.filters.bind_events();
        
        // Load filters
        EVEthing.filters.load_filters(EVEthing.wallet_journal.filters);

        // Bind aggregate button
        $('#aggregate-form').submit(function () {
            var action = $(this).attr('action');
            var data = $('#filter-form, #aggregate-form').serialize();
            window.location.href = action + '?' + data;
            return false;
        });
    }
};
