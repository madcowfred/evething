EVEthing.industry = {
    onload: function() {
        // Enable linking to a tab with a #location
        var prefix = 'tab_';
        var hash = document.location.hash;
        if (hash) {
            $('.nav-tabs a[href=' + hash.replace('#', '#' + prefix) + ']').tab('show');
        }
        
        // Change window hash for page reload
        $('.nav-tabs a').on('shown', function (e) {
            window.location.hash = e.target.hash.replace('#' + prefix, '#');
        });
    }
}
