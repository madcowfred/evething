EVEthing.assets = {
    onload: function () {
        // Bind filter events
        EVEthing.filters.bind_events();

        // Load filters
        EVEthing.filters.load_filters(EVEthing.assets.filters);

        $('.assets-sidenav').affix({offset: EVEthing.assets.side_offset});
    },

    // Magic object with a function to calculate the sidenav offset
    side_offset: {
        top: function () {
            var window_h = window.innerHeight,
                sidenav_h = $('#sidenav').height();

            if (window_h >= (sidenav_h + 75)) {
                return $('#sidenav-container').offset().top - 50;
            }
            return 999999;
        }
    },

    filter_onload: function () {
        // Bind the asset expander buttons
        $(".asset-expand").on('click', function () {
            var $this = $(this);

            if ($this.hasClass('fa-chevron-right')) {
                $this.addClass('fa-chevron-down').removeClass('fa-chevron-right');
                $($this.attr('data-target')).show();
            } else {
                $this.addClass('fa-chevron-right').removeClass('fa-chevron-down');
                $($this.attr('data-target')).hide();
            }
        });

        $('#collapse-all').on('click', function () {
            var assets = $('.asset-collapse'),
                expand = $('.asset-expand');
            expand.addClass('fa-chevron-right').removeClass('fa-chevron-down');
            assets.hide();
        });

        $('#expand-all').on('click', function () {
            var assets = $('.asset-collapse'),
                expand = $('.asset-expand');
            expand.addClass('fa-chevron-down').removeClass('fa-chevron-right');
            assets.show();
        });

        // Bind the ship EFT fitting buttons
        $(".asset-eft").on('click', function () {
            var $this = $(this),
                data_target = $('span:nth-child(1)', $this.parent()).attr('data-target'),
                ship_type = $.trim($('.asset-ship-type', $this.parent()).text()),
                ship_name = $.trim($('.asset-ship-name', $this.parent()).text()),
                last_slot = null,
                text;

            if (! ship_name) {
                ship_name = 'From Assets';
            }

            text = '[' + ship_type + ', ' + ship_name + ']\n';

            $(data_target).each(function () {
                var slot = $.trim($('td:nth-child(4)', $(this)).text());
                if (slot.substr(-4) == "Slot") {
                    if (last_slot && last_slot != slot) {
                        text += '\n';
                    }
                    last_slot = slot;

                    var name = $.trim($('td:nth-child(2)', $(this)).text());
                    text += name + '\n';
                }
            });

            $('#eft-textarea').val(text);

            $('#eft-modal').modal('show');
        });

        // Select the EFT textarea when the modal is shown
        $('#eft-modal').on('shown', function () {
            $('#eft-textarea').select();
        });
    }
};
