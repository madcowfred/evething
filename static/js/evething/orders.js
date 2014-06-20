EVEthing.orders = {
    onload: function () {
        // make tooltips appear to the right of icons
        $("[rel=tooltip]").each(function () {
            $(this).data('bs.tooltip').options.placement = 'right';
        });
    }
};
