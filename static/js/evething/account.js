EVEthing.account = {
    savedTD: null,
    savedHTML: null,

    masks: {
        2: 'AssetList',
        8: 'CharacterSheet',
        128: 'IndustryJobs',
        4096: 'MarketOrders',
        262144: 'SkillQueue',
        524288: 'Standings',
        2097152: 'WalletJournal',
        4194304: 'WalletTransactions',
        33554432: 'AccountStatus',
        67108864: 'Contracts',
        134217728: 'Locations',
    },

    onload: function() {
        EVEthing.misc.setup_tab_hash();

        // Bind apikey edit name icon
        $('#key-table').on('click', '.js-edit-name, .js-edit-group-name', function(event) {
            $('#key-table form').remove();

            var keyid = $(this).parents('tr').attr('data-id');
            var keyname = $(this).parent().text();

            if (EVEthing.account.savedTD) {
                $(EVEthing.account.savedTD).html(EVEthing.account.savedHTML);
                EVEthing.account.savedTD = null;
                EVEthing.account.savedHTML = null;
            }
            EVEthing.account.savedTD = $(this).parent();
            EVEthing.account.savedHTML = EVEthing.account.savedTD.html();

            if ($(this).hasClass('js-edit-group-name')) {
                var fieldname = 'group_name';
                var dont_edit = 'name';
            }
            else {
                var fieldname = 'name';
                var dont_edit = 'group_name';
            }

            var html = [];
            /*html.push('<form action="{{ url('thing.views.account_apikey_edit') }}" method="POST" class="form-inline nomargin">');
            html.push("{{ csrf() }}");
            html.push('<input type="hidden" class="nomargin" name="apikey_id" value="' + keyid + '">');
            html.push('<input type="hidden" class="nomargin" name="dont_edit" value="' + dont_edit + '">');
            html.push('<input type="text" class="nomargin input-medium" name="' + fieldname + '" id="magic_keyname" value="' + $.trim(keyname) + '">');
            html.push('</form>');*/

            $(this).parent().html(html.join(''));
            $('#magic_keyname').focus();
        });

        // Bind apikey delete icons
        $('#key-table').on('click', '.js-delete', function(event) {
            var keyid = $(this).parents('tr').attr('data-id');
            var keyname = $.trim($('td:nth-child(5)', $(this).parents('tr')).text());
            $('#delete-keyid-input').val(keyid);
            $('#delete-keyid').text(keyid);
            $('#delete-keyname').text(keyname);
        });

        // Bind apikey purge icons
        $('#key-table').on('click', '.js-purge', function(event) {
            var keyid = $(this).parents('tr').attr('data-id');
            var keyname = $.trim($('td:nth-child(5)', $(this).parents('tr')).text());
            $('#purge-keyid-input').val(keyid);
            $('#purge-keyid').text(keyid);
            $('#purge-keyname').text(keyname);
        });

        // Bind skillplan edit icons
        $('.edit-skillplan').on('click', function(event) {
            var sp_id = $(this).parents('tr').attr('data-id');
            var sp_name = $('td:nth-child(2)', $(this).parents('tr')).text();
            var sp_vis = $(this).parents('tr').attr('data-vis');
            $('#edit-skillplan-id').val(sp_id);
            $('#edit-skillplan-name').val(sp_name);
            $('#edit-skillplan-visibility').val(sp_vis);
        });

        // Bind skillplan delete icons
        $('.delete-skillplan').on('click', function(event) {
            var sp_id = $(this).parents('tr').attr('data-id');
            var sp_name = $('td:nth-child(2)', $(this).parents('tr')).text();
            $('#delete-skillplan-id').val(sp_id);
            $('#delete-skillplan-name').text(sp_name);
        });

        // Bind apikey build table magic
        $('#build-table').on('change', '.apikey-build', EVEthing.account.build_apikey);
        EVEthing.account.build_apikey();
    },

    build_apikey: function() {
        $('#apikey-required').empty();

        var n = 0;
        $('.apikey-build:checked').each(function() {
            masks = $(this).attr('data-masks').split(';');
            for (i in masks) {
                mask = parseInt(masks[i]);
                if ((n & mask) == 0) {
                    n += mask;
                    $('#apikey-required').append('<li>' + EVEthing.account.masks[mask] + '</li>');
                }
            }
        });
        $('#apikey-link').attr('href', 'https://community.eveonline.com/support/api-key/CreatePredefined?accessMask=' + n);
        
        if (n == 0) {
            $('#apikey-required').append('<li>None</li>');
        }
    },
}
