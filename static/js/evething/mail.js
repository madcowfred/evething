EVEthing.mail = {
    onload: function() {
        // Register Handlebars helpers
        Handlebars.registerHelper('rowClass', function() {
            if (! this.read) {
                return new Handlebars.SafeString(' class="mail-unread"');
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
                    html += '<i class="icon-something"></i> ' + corp.name;
                }
                else {
                    var alliance = EVEthing.mail.data.alliances[this.to_corp_or_alliance_id];
                    if (alliance !== undefined) {
                        html += '<i class="icon-something"></i> ' + alliance.name;
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
