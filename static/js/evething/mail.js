EVEthing.mail = {
    onload: function() {
        // Filter changes
        $('#mail-side').on('click', '.js-filter', function() {
            setTimeout(EVEthing.mail.build_table, 1);
        });
        $('#mail-side').on('change', 'select', EVEthing.mail.build_table);

        // Mark read button
        $('#mail-mark-read-button').on('click', EVEthing.mail.mark_read_click);

        // Mail all checkbox click
        $('#mail-list-check-all').on('click', EVEthing.mail.mail_check_all_click);

        // Mail link click
        $('#mail-list-table').on('click', '.mail-link', EVEthing.mail.mail_link_click);

        // Window resize
        $(window).on('resize', EVEthing.mail.resize);
        EVEthing.mail.resize();

        // Build character list
        var options = '<option value="0" selected>-ALL-</option><option value="-" disabled>——————————</option>';
        $.each(EVEthing.util.sorted_keys_by_value(EVEthing.mail.characters), function(i, character_id) {
            options += '<option value="' + character_id + '">' + EVEthing.mail.characters[character_id] + '</option>';
        });
        $('#filter-character').html(options);

        // Activate tablesorter
        $('#mail-list-table').tablesorter({
            theme: 'bootstrap',
            headerTemplate: '{content} {icon}',
            widgets: ['uitheme'],
            headers: {
                0: { sorter: false, },
            },
            sortList: [[4, 1]],
        });

        // Retrieve mail headers
        $.get(
            EVEthing.mail.headers_url,
            function(data) {
                EVEthing.mail.data = data;
                EVEthing.mail.data.message_map = {};

                for (var i = 0; i < data.messages.length; i++) {
                    message = data.messages[i];
                    EVEthing.mail.data.message_map[message.message_id] = message;

                    // Mailing list
                    if (message.to_list_id > 0) {
                        var list = EVEthing.mail.data.mailing_lists[message.to_list_id] || '*UNKNOWN LIST*';
                        message.to_list = '<i class="icon-list"></i> ' + list;
                    }
                    // Corp or alliance
                    else if (message.to_corp_or_alliance_id > 0) {
                        var corp = EVEthing.mail.data.corporations[message.to_corp_or_alliance_id];
                        // Corp
                        if (corp !== undefined) {
                            message.to_corporation = '<i class="icon-group"></i> ' + corp.name;
                        }
                        // Alliance
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
                    // Character
                    else {
                        if (message.to_characters.length > 0) {
                            if (message.to_characters.length > 1) {
                                message.to_character = '*Multiple characters*';
                            }
                            else {
                                message.to_character = EVEthing.mail.data.characters[message.to_characters[0]] || '*UNKNOWN*';
                            }
                        }
                        else {
                            message.to_character = EVEthing.mail.data.characters[message.character_id] || '*UNKNOWN*';
                        }
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
        Handlebars.registerHelper('subjectText', function() {
            return this.title || '*BLANK SUBJECT*';
        })
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

            // Early exit
            if (keep === false) {
                continue;
            }

            // Display this based on selected character?
            if (character_id > 0 && (
                message.character_id !== character_id &&
                message.to_characters.indexOf(character_id) < 0
            )) {
                keep = false;
            }

            // Early exit
            if (keep === false) {
                continue;
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

        // Reset the all checkbox to unchecked
        $('#mail-list-check-all').prop('checked', false);

        // Let tablesorter know that we've updated
        $('#mail-list-table').trigger('update');
    },

    mark_read_click: function() {
        var $form = $('#mail-mark-read-form');

        // Submit the form
        $.post(
            $form.attr('action'),
            $form.serialize(),
            function(data) {
                $.each($('#mail-list-table tbody input:checked'), function(i, input) {
                    var message_id = $(input).closest('tr').attr('data-message-id');
                    EVEthing.mail.data.message_map[message_id].read = true;
                });

                EVEthing.mail.build_table();
            }
        );
    },

    mail_check_all_click: function() {
        if ($('#mail-list-check-all').is(':checked')) {
            $('#mail-list-table tbody input').prop('checked', 'checked');
        }
        else {
            $('#mail-list-table tbody input').prop('checked', false);
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
                $('#mail-message-from').html(EVEthing.mail.data.characters[message.sender_id] || '*UNKNOWN*');
                $('#mail-message-subject').html(message.title);
                $('#mail-message-date').html(message.sent_date);

                // To is annoying
                var html = message.to_list || message.to_alliance || message.to_corporation;
                if (html === undefined) {
                    var chars = [];
                    for (var i = 0; i < message.to_characters.length; i++) {
                        var char_id = message.to_characters[i];
                        // Make our character names bold
                        if (EVEthing.mail.characters[char_id] !== undefined) {
                            chars.push('<strong>' + EVEthing.mail.characters[char_id] + '</strong>');
                        }
                        else {
                            chars.push(EVEthing.mail.data.characters[char_id] || '*UNKNOWN*');
                        }
                    }
                    html = chars.join(', ');
                }
                $('#mail-message-to').html(html);

                // If we already have a body, display it!
                if (message.body !== undefined) {
                    $('#mail-message.body').html(message.body);
                }
                else {
                    // Loading spinner in the body for now
                    $('#mail-message-body').html('<i class="icon-spinner icon-spin icon-4x"></i>');

                    // Fetch the message body
                    var url = EVEthing.mail.body_url.replace('0000', message_id);
                    $.get(
                        url,
                        function(data) {
                            if (data.body) {
                                $tr.removeClass('warning');

                                message.body = data.body.replace(/\n/g, '<br>\n');
                                message.read = true;

                                $('#mail-message-body').html(message.body);

                                EVEthing.mail.build_table();
                            }
                            // Error probably
                            else {
                                $('#mail-message.body').html('<strong>ERROR:</strong> ' + data.error);
                            }
                        }
                    );
                }

                break;
            }
        }

        return false;
    },
};
