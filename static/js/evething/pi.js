EVEthing.pi = {
    onload: function () {
        $('.pi-sidenav').affix({offset: EVEthing.pi.side_offset});
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
    }
};
