EVEthing.mail = {
    onload: function() {
        // Mail link click
        $('#mail-list-table').on('click', '.mail-link', EVEthing.mail.mail_link_click);

        $('#mail-side').on('click', '.btn, input', function() {
            setTimeout(EVEthing.mail.build_table, 1);
        });

        // Window resize
        EVEthing.mail.resize();

        // Register Handlebars helpers
        Handlebars.registerHelper('rowClass', function() {
            if (! this.read) {
                return new Handlebars.SafeString(' class="warning"');
            }
            else {
                return '';
            }
        });
        Handlebars.registerHelper('toText', function() {
            var html = EVEthing.mail.corp_or_alliance_id(this);
            if (html === '') {
                html += EVEthing.mail.data.characters[this.character_id];
            }
            return new Handlebars.SafeString(html);
        });
        Handlebars.registerHelper('senderText', function() {
            return EVEthing.mail.data.characters[this.sender_id] || '*UNKNOWN*';
        });

        // Retrieve mail headers
        $.get(
            EVEthing.mail.headers_url,
            function(data) {
                EVEthing.mail.data = data;
                EVEthing.mail.build_table();
            }
        );
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
        console.log('build table');
        var template = Handlebars.getTemplate('mail_list');

        // Collect filter settings
        var filter_unread = $('#filter-unread').hasClass('active');
        var filter_read = $('#filter-read').hasClass('active');

        var html = '';
        for (var i = 0; i < EVEthing.mail.data.messages.length; i++) {
            var message = EVEthing.mail.data.messages[i];

            var keep = false;
            if (filter_unread && !message.read) {
                keep = true;
            }
            if (filter_read && message.read) {
                keep = true;
            }

            if (keep === true) {
                html += template(message);
            }
        }

        $('#mail-list-table tbody').html(html);
    },

    // Handle corp_or_alliance_id ugh
    corp_or_alliance_id: function(message) {
        if (message.to_corp_or_alliance_id > 0) {
            var corp = EVEthing.mail.data.corporations[message.to_corp_or_alliance_id];
            if (corp !== undefined) {
                return '<i class="icon-group"></i> ' + corp.name;
            }
            else {
                var alliance = EVEthing.mail.data.alliances[message.to_corp_or_alliance_id];
                if (alliance !== undefined) {
                    return '<i class="icon-hospital"></i> ' + alliance.name;
                }
                else {
                    return '*UNKNOWN*';
                }
            }
        }
        else {
            return '';
        }
    },

    mail_link_click: function(e) {
        if (e.preventDefault) {
            e.preventDefault();
        }

        // save the table row for later
        var $tr = $(this).closest('tr');
        console.log($tr);

        var message_id = parseInt($(this).attr('href').replace('#', ''));
        for (var i = 0; i < EVEthing.mail.data.messages.length; i++) {
            message = EVEthing.mail.data.messages[i];

            if (message.message_id === message_id) {
                // Fill in the data we already have
                $('#mail-message-from').html(EVEthing.mail.data.characters[this.sender_id] || '*UNKNOWN*');
                $('#mail-message-subject').html(message.title);
                $('#mail-message-date').html(message.sent_date);

                // To is annoying
                var html = EVEthing.mail.corp_or_alliance_id(message);
                if (html === '') {
                    var chars = [];
                    for (var i = 0; i < message.to_characters.length; i++) {
                        chars.push(EVEthing.mail.data.characters[message.to_characters[i]] || '*UNKNOWN*');
                    }
                    html += chars.join(', ');
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
