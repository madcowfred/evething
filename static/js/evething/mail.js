EVEthing.mail = {
    onload: function() {
        // Mail link click
        $('#mail-list-table').on('click', '.mail-link', function(e) {
            if (e.preventDefault) {
                e.preventDefault();
            }

            var message_id = parseInt($(this).attr('href').replace('#', ''));
            for (var i = 0; i < EVEthing.mail.data.messages.length; i++) {
                message = EVEthing.mail.data.messages[i];

                if (message.message_id === message_id) {
                    // Fill in the data we already have
                    $('#mail-message-from').html(EVEthing.mail.data.characters[this.sender_id] || '*UNKNOWN*');
                    //$('#mail-message-to');
                    $('#mail-message-subject').html(message.title);
                    $('#mail-message-date').html(message.sent_date);

                    // Loading spinner in the body for now
                    $('#mail-message-body').html('<i class="icon-spinner icon-spin icon-4x"></i>');

                    // Fetch the message body
                    var url = EVEthing.mail.body_url.replace('0000', message_id);
                    $.get(
                        url,
                        function(data) {
                            if (data.body) {
                                $('#mail-message-body').html(data.body.replace('\n', '<br>\n'));
                            }
                            // Error probably
                            else {
                                $('#mail-message.body').html('<strong>ERROR:</strong> ' + data.error);
                            }
                        }
                    );

                    console.log(message);
                    break;
                }
            }

            return false;
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
            var html = '';
            if (this.to_corp_or_alliance_id > 0) {
                var corp = EVEthing.mail.data.corporations[this.to_corp_or_alliance_id];
                if (corp !== undefined) {
                    html += '<i class="icon-group"></i> ' + corp.name;
                }
                else {
                    var alliance = EVEthing.mail.data.alliances[this.to_corp_or_alliance_id];
                    if (alliance !== undefined) {
                        html += '<i class="icon-hospital"></i> ' + alliance.name;
                    }
                    else {
                        html += '*UNKNOWN*';
                    }
                }
            }
            else {
                html += '<i class="icon-something"></i> ' + EVEthing.mail.data.characters[this.character_id];
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
        var template = Handlebars.getTemplate('mail_list');
        var html = '';
        for (var i = 0; i < EVEthing.mail.data.messages.length; i++) {
            var message = EVEthing.mail.data.messages[i];
            html += template(message);
        }

        $('#mail-list-table tbody').html(html);
    },
};
