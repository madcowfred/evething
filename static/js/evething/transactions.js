EVEthing.transactions = {
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

        // Bind filter events
        EVEthing.filters.bind_events();
        
        // Load filters
        EVEthing.filters.load_filters(EVEthing.transactions.filters);
    }
};
