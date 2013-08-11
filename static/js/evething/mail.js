EVEthing.mail = {
    onload: function() {
        // Filter changes
        $('#mail-side').on('click', '.btn, input', function() {
            setTimeout(EVEthing.mail.build_table, 1);
        });
        $('#mail-side').on('change', 'select', EVEthing.mail.build_table);

        // Mail link click
        $('#mail-list-table').on('click', '.mail-link', EVEthing.mail.mail_link_click);

        // Window resize
        $(window).on('resize', EVEthing.mail.resize);
        EVEthing.mail.resize();

        // Build character list
        var options = '<option value="0">-ALL-</option><option value="-" disabled>——————————</option>';
        $.each(EVEthing.util.sorted_keys_by_value(EVEthing.mail.characters), function(i, character_id) {
            options += '<option value="' + character_id + '">' + EVEthing.mail.characters[character_id] + '</option>';
        });
        $('#filter-character').html(options);
        $('#filter-character').val(0);

        // Retrieve mail headers
        $.get(
            EVEthing.mail.headers_url,
            function(data) {
                EVEthing.mail.data = data;

                for (var i = 0; i < data.messages.length; i++) {
                    message = data.messages[i];

                    if (message.to_list_id > 0) {
                        message.to_list = EVEthing.mail.data.mailing_lists[message.to_list_id] || '*UNKNOWN LIST*';
                    }
                    else if (message.to_corp_or_alliance_id > 0) {
                        var corp = EVEthing.mail.data.corporations[message.to_corp_or_alliance_id];
                        if (corp !== undefined) {
                            message.to_corporation = '<i class="icon-group"></i> ' + corp.name;
                        }
                        else {
                            var alliance = EVEthing.mail.data.alliances[message.to_corp_or_alliance_id];
                            if (alliance !== undefined) {
                                message.to_alliance = '<i class="icon-hospital"></i> ' + alliance.name;
                            }
                            else {
                                message.to_alliance = '<i class="icon-hospital"></i> *UNKNOWN*';
                            }
                        }
                    }
                    else {
                        message.to_character = EVEthing.mail.data.characters[message.character_id] || '*UNKNOWN*';
                    }
                }

                EVEthing.mail.build_table();
            }
        );

        // Register Handlebars helpers
        Handlebars.registerHelper('rowClass', function() {
            if (this.read) {
                return new Handlebars.SafeString(' class="success"');
            }
            else {
                return new Handlebars.SafeString(' class="error"');
            }
        });
        Handlebars.registerHelper('toText', function() {
            return new Handlebars.SafeString(this.to_list || this.to_alliance || this.to_corporation || this.to_character);
        });
        Handlebars.registerHelper('senderText', function() {
            return EVEthing.mail.data.characters[this.sender_id] || '*UNKNOWN*';
        });
    },

    // Resize event
    resize: function(e) {
        var h = ($('#wrap').height() - $('#wrap .navbar').height() - $('#footer').height() - 40) / 2;
        var props = { 'min-height': h + 'px', 'max-height': h + 'px' };
        $('.mail-list').css(props);
        $('.mail-message').css(props);
    },

    // Build mail-list-table
    build_table: function() {
        var template = Handlebars.getTemplate('mail_list');

        // Collect filter settings
        var filter_unread = $('#filter-unread').hasClass('active');
        var filter_read = $('#filter-read').hasClass('active');
        var filter_to_character = ($('#filter-to-character').is(':checked'));
        var filter_to_corporation = ($('#filter-to-corporation').is(':checked'));
        var filter_to_alliance = ($('#filter-to-alliance').is(':checked'));
        var filter_to_mailing_list = ($('#filter-to-mailing-list').is(':checked'));

        var character_id = parseInt($('#filter-character').val());

        var count = 0;
        var html = '';
        for (var i = 0; i < EVEthing.mail.data.messages.length; i++) {
            var message = EVEthing.mail.data.messages[i];
            var keep = true;

            // Display this based on read/unread state?
            var keep_read = false;
            if (filter_unread && !message.read) {
                keep_read = true;
            }
            if (filter_read && message.read) {
                keep_read = true;
            }
            keep = keep_read;

            // Display this based on selected character?
            if (character_id > 0 && (
                message.character_id !== character_id &&
                message.to_characters.indexOf(character_id) < 0
            )) {
                keep = false;
            }

            // Display this based on to: filters?
            keep_to = false;
            if ((filter_to_character && message.to_character) ||
                (filter_to_corporation && message.to_corporation) ||
                (filter_to_alliance && message.to_alliance) ||
                (filter_to_mailing_list && message.to_list)) {
                keep_to = true;
            }
            if (keep === true) {
                keep = keep_to;
            }

            // Add to page if we should display it
            if (keep === true) {
                count++;
                html += template(message);
            }
        }

        // Add the rows to the table
        $('#mail-list-table tbody').html(html);

        // Show/hide the filtered row if we have to
        if (count === 0) {
            $('#mail-list-filtered').show();
        }
        else {
            $('#mail-list-filtered').hide();
        }
    },

    mail_link_click: function(e) {
        if (e.preventDefault) {
            e.preventDefault();
        }

        // save the table row for later
        var $tr = $(this).closest('tr');

        var message_id = parseInt($(this).attr('href').replace('#', ''));
        for (var i = 0; i < EVEthing.mail.data.messages.length; i++) {
            message = EVEthing.mail.data.messages[i];

            if (message.message_id === message_id) {
                // Fill in the data we already have
                $('#mail-message-from').html(EVEthing.mail.data.characters[this.sender_id] || '*UNKNOWN*');
                $('#mail-message-subject').html(message.title);
                $('#mail-message-date').html(message.sent_date);

                // To is annoying
                var html = message.to_list || message.to_alliance || message.to_corporation;
                if (html === undefined) {
                    var chars = [];
                    for (var i = 0; i < message.to_characters.length; i++) {
                        chars.push(EVEthing.mail.data.characters[message.to_characters[i]] || '*UNKNOWN*');
                    }
                    html = chars.join(', ');
                }
                $('#mail-message-to').html(html);

                // Loading spinner in the body for now
                $('#mail-message-body').html('<i class="icon-spinner icon-spin icon-4x"></i>');

                // Fetch the message body
                var url = EVEthing.mail.body_url.replace('0000', message_id);
                $.get(
                    url,
                    function(data) {
                        if (data.body) {
                            $tr.removeClass('warning');
                            $('#mail-message-body').html(data.body.replace(/\n/g, '<br>\n'));
                            message.read = true;
                            EVEthing.mail.build_table();
                        }
                        // Error probably
                        else {
                            $('#mail-message.body').html('<strong>ERROR:</strong> ' + data.error);
                        }
                    }
                );

                break;
            }
        }

        return false;
    },
};
