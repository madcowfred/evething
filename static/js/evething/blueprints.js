EVEthing.blueprints = {
    onload: function () {
        $('#checkall').on('click', function () {
            $('.js-check').prop('checked', this.checked ? 'checked' : false);
        });

        // bind the edit buttons
        $('.bp-edit').on('click', function () {
            var $tr = $(this).parents('tr');
            $('#bp-edit-bpi_id').attr('value', $tr.find('td').eq(0).text());
            $('#bp-edit-name').val($tr.find('td').eq(1).text());
            $('#bp-edit-ml').val($tr.find('td').eq(3).text());
            $('#bp-edit-pl').val($tr.find('td').eq(4).text());
            $('#edit-blueprint').modal('show');
        });

        // bind the delete buttons
        $('.bp-delete').on('click', function () {
            $tr = $(this).parents('tr');
            $('#bp-del-bpi_id').attr('value', $tr.find('td').eq(0).text());
            $('#bp-del-id').text($tr.find('td').eq(0).text());
            $('#bp-del-name').text($tr.find('td').eq(1).text());
            $('#bp-del-type').text($tr.find('td').eq(2).text());
            $('#bp-del-ml').text($tr.find('td').eq(3).text());
            $('#bp-del-pl').text($tr.find('td').eq(4).text());
            $('#del-blueprint').modal('show');
        });

        // call the tablesorter plugin
        /*$("#blueprints-table").tablesorter({
            'headers': {
                2: { sorter: false },
                3: { sorter: false },
                4: { sorter: false },
                5: { sorter: false },
                6: { sorter: false },
                7: { sorter: 'human' },
                8: { sorter: 'human' },
                9: { sorter: 'human' },
                10: { sorter: 'human' },
                11: { sorter: 'human' },
                12: { sorter: false },
            },
            'sortList': [[0, 1]],
        });*/
    }
};
