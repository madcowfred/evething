EVEthing.character = {
    anon_checked: null,
    sidenav_top: 0,

    onload: function() {
        EVEthing.misc.setup_tab_hash();

        // Bind skillplans toggle
        $('#skillplans-toggle').on('click', function() {
            $('#skillplans-personal').toggle();
            $('#skillplans-global').toggle();
        });

        // Bind settings toggle
        $('#settings-toggle').on('click', function() {
            $('#settings-box').toggle();
        });

        // Bind enable/disable of all public sub-checkboxes when public changes
        $("#public-checkbox").change(EVEthing.character.public_checkbox_change);
        EVEthing.character.public_checkbox_change();

        // Bind magic toggle thing for anonymous keys
        $("#anon-toggle").change(EVEthing.character.anon_toggle);
        EVEthing.character.anon_toggle($('#anon-toggle'));

        // AJAX for settings form
        $('#settings-form').on('submit', EVEthing.character.settings_submit);
    },

    public_checkbox_change: function (initial) {
        var checked = this.checked;

        if (initial === undefined || initial === null) {
            checked = $("#public-checkbox").is(':checked');
        }

        if (checked) {
            $('.disable-toggle').removeAttr("disabled");
        }
        else {
            $('.disable-toggle').attr("disabled", "disabled");
        }
    },

    anon_toggle: function() {
        if ($('#anon-toggle').is(':checked')) {
            var anon_key = $('#anon-key').val();
            if (anon_key !== '') {
                var html = '<a href="' + EVEthing.character.anon_url.replace('zzzz', anon_key) + '">Anonymized link</a>';
                $('#anon-key-label').html(html);
            }
            else {
                $('#anon-key-label').html('<span class="glyphicon glyphicon-anchor"></span> Save to get new link');
            }
        }
        else {
            $('#anon-key-label').empty();
        }
    },

    settings_submit: function(e) {
        if (e.preventDefault) {
            e.preventDefault();
        }

        $('#settings-status').html('<span class="glyphicon glyphicon-spinner icon-spin"></span> Saving...');

        // Submit the form
        $.post(
            $(this).attr('action'),
            $(this).serialize(),
            function(data) {
                if (typeof data === 'object') {
                    $('#anon-key').val(data.anon_key);
                    $('#settings-status').html('<span class="glyphicon glyphicon-ok"></span> Saved!');
                    EVEthing.character.anon_toggle();
                }
                // Anything not an object = error
                else {
                    $('#settings-status').html('<span class="glyphicon glyphicon-remove"></span> Error!');
                }
            }
        );

        return false;
    },
}
