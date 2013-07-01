EVEthing.character = {
    anon_checked: null,
    
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

        $("#public-checkbox").change(EVEthing.character.public_checkbox_change);
        EVEthing.character.public_checkbox_change();

        EVEthing.character.anon_checked = $('#anon-key').attr('checked');
        $("#anon-key").change(EVEthing.character.anon_toggle);
        EVEthing.character.anon_toggle();
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
        var checked = $('#anon-key').attr('checked');
        if (checked != EVEthing.character.anon_checked) {
            $('#anon-key-link').remove();
            EVEthing.character.anon_checked = checked;
        }

        if (checked == "checked") {
            $("#anon-key-text").removeAttr("disabled");
            /*if ($("#anon-key-text").val() == "") {
                $("#anon-key-text").val(randString(16));
            }*/
        }
        else {
            $("#anon-key-text").attr("disabled", "");
            $("#anon-key-text").val("");
        }
    }
}
