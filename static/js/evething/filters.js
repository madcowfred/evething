EVEthing.filters = {
    // Comparison 
    comparisons: {
        'eq': '==',
        'ne': '!=',
        'gt': '>',
        'gte': '>=',
        'lt': '<',
        'lte': '<=',
        'in': 'contains',
        'bt': 'between',
    },

    bind_events: function() {
        // click event for add icon
        $('#filters').on('click', '.js-add', function() {
            $('#filters').append(EVEthing.filters.build());
            $('.date').datepicker();
        });

        // click event for delete icon
        $('#filters').on('click', '.js-delete', function() {
            $(this).parent().remove();
            if ($('.filter-type').length == 0) {
                $('#filters').append(EVEthing.filters.build());
            }
        });

        // change event for filter-type selects
        $('#filters').on('change', '.filter-type', function() {
            var $ft = $(this);
            // clear any other select/input in this line
            $ft.siblings('select, input').remove();
            // add the comparison box
            $ft.after(EVEthing.filters.build_comparison($ft.val(), undefined));
            // add the value box
            var $fc = $ft.next();
            $fc.after(EVEthing.filters.build_value($ft.val(), $fc.val(), ''));
            $('.date').datepicker();
        });

        // change event for filter-comp selects
        $('#filters').on('change', '.filter-comp', function() {
            var $ft = $(this).prev();
            var $fc = $(this);
            var $fv = $fc.next();
            
            var val = $fc.val();
            if (
                (val === 'in' && ! $fv.is('input')) ||
                (val === 'bt') ||
                (val !== 'in' && val !== 'bt' && ! $fv.is('select'))
            ) {
                $fv.remove();
                $fc.after(EVEthing.filters.build_value($ft.val(), $fc.val(), ''));
                $('.date').datepicker();
            }
        });

        // change event for datepicker disasters
        $('#filters').on('changeDate', '.date', function(ev) {
            var $span = $('span:first', $(this).parent().parent());
            var dates = [];
            $.each($('input[type="text"]', $span), function(index, input) {
                dates.push($(input).val());
            });
            $('input[type="hidden"]', $span).val(dates.join());
        });

        $('.date').datepicker();
    },

    load_filters: function(filters) {
        // Add our provided filters
        var count = 0;
        $.each(filters, function(ft, fcfvs) {
            for (var i = 0; i < fcfvs.length; i++) {
                $('#filters').append(EVEthing.filters.build(ft, fcfvs[i][0], fcfvs[i][1]));
                count++;
            }
        });
        // If we didn't add any filters, make an empty one
        if (count === 0) {
            $('#filters').append(EVEthing.filters.build());
        }
    },

    build: function(ft, fc, fv) {
        var html = '<div class="control-group" style="margin: 0;">';
        html += '<select name="ft" class="filter-type input-medium">';
        html += '<option value=""></option>';

        $.each(EVEthing.util.sorted_keys(EVEthing.filters.expected), function(i, k) {
            if (k === ft) {
                html += '<option value="' + k + '" selected>' + EVEthing.filters.expected[k].label + '</option>';
            }
            else {
                html += '<option value="' + k + '">' + EVEthing.filters.expected[k].label + '</option>';
            }
        });
        html += '</select>';

        if (ft) {
            html += EVEthing.filters.build_comparison(ft, fc);
            html += EVEthing.filters.build_value(ft, fc, fv);
        }

        html += '&nbsp;<i class="js-add icon-plus clickable filter-icon"></i>';
        html += '<i class="js-delete icon-trash clickable filter-icon"></i>';
        html += '</div>';

        return html;
    },

    build_comparison: function(ft, fc) {
        html = ' <select name="fc" class="filter-comp input-small">';

        for (var k in EVEthing.filters.expected[ft].comps) {
            var v = EVEthing.filters.expected[ft].comps[k];
            if (v == fc) {
                html += '<option value="' + v + '" selected>' + EVEthing.filters.comparisons[v] + '</option>';
            }
            else {
                html += '<option value="' + v + '">' + EVEthing.filters.comparisons[v] + '</option>';
            }
        }

        html += '</select>';
        return html;
    },

    build_value: function(ft, fc, fv) {
        html = ' ';

        if (fc == 'in') {
            html += '<input name="fv" class="filter-value span2" type="text" value="' + fv + '">';
        }
        else if (ft == 'date') {
            dates = fv.split(',');
            for (var i = dates.length; i < 2; i++) {
                dates.push('');
            }

            html += '<span>';
            html += '<div class="input-append date" data-date="' + dates[0] + '" data-date-format="yyyy-mm-dd">';
            html += '<input type="text" class="input-small" value="' + dates[0] + '" readonly>';
            html += '<span class="add-on"><i class="icon-calendar"></i></span></div>';
            if (fc == 'bt') {
                html += ' and ';
                html += '<div class="input-append date" data-date="' + dates[1] + '" data-date-format="yyyy-mm-dd">';
                html += '<input type="text" class="input-small" value="' + dates[1] + '" readonly>';
                html += '<span class="add-on"><i class="icon-calendar"></i></span></div>';
            }
            html += '<input type="hidden" name="fv" value="">';
            html += '</span>';
        }
        else if (EVEthing.filters.data[ft]) {
            html += '<select name="fv" class="filter-value span2">';

            $.each(EVEthing.util.sorted_keys_by_value(EVEthing.filters.data[ft]), function(i, d_id) {
                var d_name = EVEthing.filters.data[ft][d_id];
                if (d_id == fv) {
                    html += '<option value="' + d_id + '" selected>' + d_name + '</option>';
                }
                else {
                    html += '<option value="' + d_id + '">' + d_name + '</option>';
                }
            });

            html += '</select>';
        }
        else {
            html += '<input name="fv" class="filter-value span2" type="text" value="' + fv + '">';
        }
        return html;
    },
}
