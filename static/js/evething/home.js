EVEthing.home = {
    // CSS class:text mapping
    replacements: {
        'character-name': 'Character Name',
        'apikey-name': 'API name',
        'corporation-name': 'Corporation Name [TICKR]',
        'character-location': 'Hoth -- X-Wing',
        'wallet-division': 'Hookers & Blow',
        'user-name': 'Mr. User',
        'security-status': '0.0'
    },

    onload: function() {
        // make tooltips appear to the right of icons
        $("[rel=tooltip]").each(function () {
            $(this).data('tooltip').options.placement = 'right';
        });

        // Bind screenshot mode button
        $('body').on('click', '.js-screenshot', EVEthing.home.screenshot_mode);
    },

    screenshot_mode: function() {
        // replace sensitive data with placeholders
        $('.sensitive').each(function () {
            var $this = $(this);
            var oldname = $this.attr('oldname');
            
            if (oldname === undefined) {
                $this.attr('oldname', $this.text());
                
                var classes = $this.attr('class').split(/\s+/);
                for (var i = 0; i < classes.length; i++) {
                    var rep = EVEthing.home.replacements[classes[i]];
                    if (rep !== undefined) {
                        $this.text(rep);
                        break;
                    }
                }
            }
            else {
                $this.text(oldname);
                $this.removeAttr('oldname');
            }
        });

        var seen_tooltips = Array();
        $('.row-fluid').each(function() {
            var $row = $(this);

            $('.well', $row).each(function() {
                var $well = $(this);
                var seen = false;

                $('[rel=tooltip]', $well).each(function () {
                    var $i = $(this);
                    if (seen == false && seen_tooltips[$i.attr('class')] === undefined) {
                        seen = true;
                        seen_tooltips[$i.attr('class')] = true;

                        if ($i.attr('shown') === undefined) {
                            $i.tooltip('show');
                            $i.attr('shown', 'yup');
                        }
                        else {
                            $i.tooltip('hide');
                            $i.removeAttr('shown');
                        }
                    }
                });
            });
        });
    },
}
