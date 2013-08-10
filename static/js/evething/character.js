EVEthing.character = {
    anon_checked: null,

    onload: function() {
        EVEthing.misc.setup_tab_hash();

        // Bind enable/disable of all public sub-checkboxes when public changes
        $("#public-checkbox").change(EVEthing.character.public_checkbox_change);
        EVEthing.character.public_checkbox_change();

        // Bind magic toggle thing for anonymous keys
        $("#anon-toggle").change(EVEthing.character.anon_toggle);
        EVEthing.character.anon_toggle($('#anon-toggle'));

        // AJAX for settings form
        $('#settings-form').on('submit', EVEthing.character.settings_submit);
    },

    public_checkbox_change: function() {
        if (this.checked) {
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
                $('#anon-key-label').html('<i class="icon-anchor"></i> Save to get new link');
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

        $('#settings-status').html('<i class="icon-spinner icon-spin"></i> Saving...');

        // Submit the form
        $.post(
            $(this).attr('action'),
            $(this).serialize(),
            function(data) {
                if (typeof data === 'object') {
                    $('#anon-key').val(data.anon_key);
                    $('#settings-status').html('<i class="icon-ok"></i> Saved!');
                    EVEthing.character.anon_toggle();
                }
                // Anything not an object = error
                else {
                    $('#settings-status').html('<i class="icon-remove"></i> Error!');
                }
            }
        );

        return false;
    },
}
