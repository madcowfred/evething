EVEthing.home = {
    // CSS class:text mapping
    REPLACEMENTS: {
        'character-name': 'Character Name',
        'apikey-name': 'API name',
        'corporation-name': 'Corporation Name [TICKR]',
        'character-location': 'Hoth -- X-Wing',
        'wallet-division': 'Hookers & Blow',
        'user-name': 'Mr. User',
    },

    PROFILE: {
        CHAR_COL_SPAN: 3,
        HOME_SHOW_LOCATIONS: true,
        HOME_SHOW_SEPARATORS: true,
    },

    SHIPS: {},
    CORPORATIONS: {},
    ALLIANCES: {},

    CHARACTERS: {},

    CHARACTER_TEMPLATE: Handlebars.getTemplate('home_character'),

    DISPLAY_ROWS: [],

    CHARACTER_ORDER: [],

    onload: function() {
        // Bind screenshot mode button
        $('body').on('click', '.js-screenshot', EVEthing.home.screenshot_mode);

        Handlebars.registerHelper('lookup', function(dict, key) {
            if (dict.hasOwnProperty(key)) return dict[key];
            return key;
        });

        Handlebars.registerHelper('roman', function(num) {
            if (!+num)
                return false;
            var digits = String(+num).split(""),
                key = ["","C","CC","CCC","CD","D","DC","DCC","DCCC","CM",
                       "","X","XX","XXX","XL","L","LX","LXX","LXXX","XC",
                       "","I","II","III","IV","V","VI","VII","VIII","IX"],
                roman = "",
                i = 3;
            while (i--)
                roman = (key[+digits.pop() + (i * 10)] || "") + roman;
            return Array(+digits.join("") + 1).join("M") + roman;
        });

        EVEthing.home.initialLoad();
    },

    'draw_characters': function() {
        if (EVEthing.home.CHARACTER_ORDER.length != EVEthing.home.CHARACTERS.length) EVEthing.home.sort_characters();

        for (var i=0; i<EVEthing.home.DISPLAY_ROWS.length; i++) {
            EVEthing.home.DISPLAY_ROWS[i].remove();
        }
        EVEthing.home.DISPLAY_ROWS = [];

        for (var i=0; i < EVEthing.home.CHARACTER_ORDER.length; i++) {
            var row_number = Math.floor(i / 4);
            if (EVEthing.home.DISPLAY_ROWS.length < row_number+1) {
                EVEthing.home.DISPLAY_ROWS[row_number] = $('<div class="row-fluid"></div>');
                $('#container').append(EVEthing.home.DISPLAY_ROWS[row_number]);
            }

            EVEthing.home.CHARACTERS[EVEthing.home.CHARACTER_ORDER[i]].render();
            EVEthing.home.DISPLAY_ROWS[row_number].append(EVEthing.home.CHARACTERS[EVEthing.home.CHARACTER_ORDER[i]].well);
        }
    },

    'character_ordering': {
        'skill_queue': function(a, b) {
            return EVEthing.home.CHARACTERS[b].character.skill_queue_duration - EVEthing.home.CHARACTERS[a].character.skill_queue_duration;
        },
    },

    'sort_characters': function() {
        if (EVEthing.home.CHARACTER_ORDER.length != EVEthing.home.CHARACTERS.length) {
            EVEthing.home.CHARACTER_ORDER = Object.keys(EVEthing.home.CHARACTERS);
        }
        var methods = [];
        for (var i in arguments) {
            if (!arguments.hasOwnProperty(i)) continue;
            methods[methods.length] = arguments[i];
        };

        if (methods.length == 0) {
            for (var i in EVEthing.home.character_ordering) {
                if (!EVEthing.home.character_ordering.hasOwnProperty(i)) continue;
                methods[methods.length] = EVEthing.home.character_ordering[i];
            }
        }

        for (var i=0; i<methods.length; i++) {
            console.log(methods[i]);
            EVEthing.home.CHARACTER_ORDER.sort(methods[i]);
        }
    },

    initialLoad: function() {
        $.get(
            'home/api',
            {
                'options': ['characters','details','corporations','alliances','skill_queues'],
            },
            EVEthing.home.handleResponse
        );
    },

    handleResponse: function(data, textStatus, jqXHR) {
        if (data.hasOwnProperty('ships')) {
            EVEthing.home.parseShips(data);
            delete data['ships'];
        }
        if (data.hasOwnProperty('alliances')) {
            EVEthing.home.parseAlliances(data);
            delete data['alliances'];
        }
        if (data.hasOwnProperty('corporations')) {
            EVEthing.home.parseCorporations(data);
            delete data['corporations']
        }

        if (data.hasOwnProperty('characters')) {
            for (var i in data.characters) {
                if (!data.characters.hasOwnProperty(i)) continue;

                if (EVEthing.home.CHARACTERS.hasOwnProperty(i)) EVEthing.home.CHARACTERS[i].update(data);

                EVEthing.home.CHARACTERS[i] = new EVEthing.home.CharacterDisplay(i, data);
            }
        }

        EVEthing.home.draw_characters();
    },

    parseShips: function(data) {
        for (var i in data.ships) {
            if (!data.ships.hasOwnProperty(i)) continue;
            EVEthing.home.SHIPS[i] = data.ships[i];
        }
    },

    parseAlliances: function(data) {
        for (var i in data.alliances) {
            if (!data.alliances.hasOwnProperty(i)) continue;
            EVEthing.home.ALLIANCES[i] = data.alliances[i];
        }
    },

    parseCorporations: function(data) {
        for (var i in data.corporations) {
            if (!data.corporations.hasOwnProperty(i)) continue;
            EVEthing.home.CORPORATIONS[i] = data.corporations[i];
        }
    },

    screenshot_mode: function() {
        // replace sensitive data with placeholders
        $('.sensitive').each(function () {
            var $this = $(this);
            var oldname = $this.attr('oldname');
            
            if (oldname === undefined) {
                $this.attr('oldname', $this.text());
                
                var classes = $this.attr('class').split(/\s+/);
                for (var i = 0; i < classes.length; i++) {
                    var rep = EVEthing.home.REPLACEMENTS[classes[i]];
                    if (rep !== undefined) {
                        $this.text(rep);
                        break;
                    }
                }
            }
            else {
                $this.text(oldname);
                $this.removeAttr('oldname');
            }
        });

        var seen_tooltips = Array();
        $('.row-fluid').each(function() {
            var $row = $(this);

            $('.well', $row).each(function() {
                var $well = $(this);
                var seen = false;

                $('[rel=tooltip]', $well).each(function () {
                    var $i = $(this);
                    if (seen == false && seen_tooltips[$i.attr('class')] === undefined) {
                        seen = true;
                        seen_tooltips[$i.attr('class')] = true;

                        if ($i.attr('shown') === undefined) {
                            $i.tooltip('show');
                            $i.attr('shown', 'yup');
                        }
                        else {
                            $i.tooltip('hide');
                            $i.removeAttr('shown');
                        }
                    }
                });
            });
        });
    },
};

/**
 * This prototype is used for displaying the characters on the home page
  */
EVEthing.home.CharacterDisplay = function(character_id, data) {
    this.character_id = character_id;

    this.well = $('<div></div>');
    this.well.addClass('span' + EVEthing.home.PROFILE.CHAR_COL_SPAN);

    this.html = null;

    if (typeof(data) != "undefined") {
        this.parseResponse(data);
    } else {
        this.load();
    }

};

EVEthing.home.CharacterDisplay.prototype.load = function() {
    // Pass
};

EVEthing.home.CharacterDisplay.prototype.update = function() {
    // Pass
};

EVEthing.home.CharacterDisplay.prototype.parseResponse = function(data) {
    this.character = data.characters[this.character_id];

    if (!this.character.hasOwnProperty('skill_queue_duration')) this.character.skill_queue_duration = 0;

    if (data.hasOwnProperty('ships')) EVEthing.home.parseShips(data);
    if (data.hasOwnProperty('alliances')) EVEthing.home.parseAlliances(data);
    if (data.hasOwnProperty('corporations')) EVEthing.home.parseCorporations(data);

    this.html = this.render();
};

EVEthing.home.CharacterDisplay.prototype.render = function() {
    this.html = $(EVEthing.home.CHARACTER_TEMPLATE({
            'character': this.character,
            'profile': EVEthing.home.PROFILE,
            'ships': EVEthing.home.SHIPS,
            'corporations': EVEthing.home.CORPORATIONS,
            'alliances': EVEthing.home.ALLIANCES
    }));

    this.html.find('[rel="popover"]').popover({'animation': false, 'trigger': 'hover', 'html': true});

    this.well.empty();
    this.well.append(this.html);
};


