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
        134217728: 'Locations'
    },

    onload: function () {
        EVEthing.misc.setup_tab_hash();

        // Bind apikey edit name icon
        $('#key-table').on('click', '.js-edit-name, .js-edit-group-name', function () {
            var html = [];

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
                var fieldname = 'group_name',
                    dont_edit = 'name';
            } else {
                var fieldname = 'name',
                    dont_edit = 'group_name';
            }

            html.push('<form action="' + account_edit_url + '" method="POST" class="form-inline nomargin">');
            html.push(csrf);
            html.push('<input type="hidden" class="nomargin" name="apikey_id" value="' + keyid + '">');
            html.push('<input type="hidden" class="nomargin" name="dont_edit" value="' + dont_edit + '">');
            html.push('<input type="text" class="nomargin input-medium" name="' + fieldname + '" id="magic_keyname" value="' + $.trim(keyname) + '">');
            html.push('</form>');

            $(this).parent().html(html.join(''));
            $('#magic_keyname').focus();
        });

        // Bind apikey delete icons
        $('#key-table').on('click', '.js-delete', function () {
            var keyid = $(this).parents('tr').attr('data-id'),
                keyname = $.trim($('td:nth-child(5)', $(this).parents('tr')).text());
            $('#delete-keyid-input').val(keyid);
            $('#delete-keyid').text(keyid);
            $('#delete-keyname').text(keyname);
        });

        // Bind apikey purge icons
        $('#key-table').on('click', '.js-purge', function () {
            var keyid = $(this).parents('tr').attr('data-id'),
                keyname = $.trim($('td:nth-child(5)', $(this).parents('tr')).text());
            $('#purge-keyid-input').val(keyid);
            $('#purge-keyid').text(keyid);
            $('#purge-keyname').text(keyname);
        });

        // Bind skillplan edit icons
        $('.edit-skillplan').on('click', function () {
            var sp_id = $(this).parents('tr').attr('data-id'),
                sp_name = $('td:nth-child(2)', $(this).parents('tr')).text(),
                sp_vis = $(this).parents('tr').attr('data-vis');
            $('#edit-skillplan-id').val(sp_id);
            $('#edit-skillplan-name').val(sp_name);
            $('#edit-skillplan-visibility').val(sp_vis);
        });

        // Bind skillplan delete icons
        $('.delete-skillplan').on('click', function () {
            var sp_id = $(this).parents('tr').attr('data-id'),
                sp_name = $('td:nth-child(2)', $(this).parents('tr')).text();
            $('#delete-skillplan-id').val(sp_id);
            $('#delete-skillplan-name').text(sp_name);
        });

        // Bind apikey build table magic
        $('#build-table').on('change', '.apikey-build', EVEthing.account.build_apikey);
        EVEthing.account.build_apikey();

        EVEthing.account.HOME_GROUP_DATALIST = $('datalist#home_groups');
        EVEthing.account.build_home_group_list();
        $('tbody.characters input[type="text"]').change(EVEthing.account.build_home_group_list);

        $.tablesorter.addParser({
            id: 'inputValueParser',
            is: function(s, table, cell) {
                return $(cell).find('input').length > 0
            },
            format: function(s, table, cell, cellIndex) {
                var input = $($(cell).find('input')[0]);
                if (input.attr('type') == 'checkbox') {
                    return (input[0].checked == true ? "0" : "1");
                }
                return input.val();
            },
            parsed: true,
            type: 'text',
        });

        $('table.characters').tablesorter({'uitheme': 'bootstrap'});
    },

    HOME_GROUP_DATALIST: null,

    build_home_group_list: function() {
        EVEthing.account.HOME_GROUP_DATALIST.empty();

        var home_groups = {};
        var inputs = $('tbody.characters input[type="text"]');
        for (var i=0; i<inputs.length; i++) {
            var item = $(inputs[i]).val();

            if (!(item in home_groups)) {
                home_groups[item] = true;
            }
        }

        home_groups = Object.keys(home_groups);
        home_groups.sort();
        for (var i in home_groups) {
            EVEthing.account.HOME_GROUP_DATALIST.append($('<option value="' + home_groups[i] + '" />'));
        }
    },

    build_apikey: function () {
        $('#apikey-required').empty();

        var n = 0;
        $('.apikey-build:checked').each(function () {
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
    }
};
