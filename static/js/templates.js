this["Handlebars"] = this["Handlebars"] || {};
this["Handlebars"]["templates"] = this["Handlebars"]["templates"] || {};

this["Handlebars"]["templates"]["mail_list"] = Handlebars.template({"compiler":[6,">= 2.0.0-beta.1"],"main":function(depth0,helpers,partials,data) {
    var helper, alias1=helpers.helperMissing, alias2="function", alias3=this.escapeExpression;

  return "                  <tr"
    + alias3(((helper = (helper = helpers.rowClass || (depth0 != null ? depth0.rowClass : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"rowClass","hash":{},"data":data}) : helper)))
    + " data-message-id=\""
    + alias3(((helper = (helper = helpers.message_id || (depth0 != null ? depth0.message_id : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"message_id","hash":{},"data":data}) : helper)))
    + "\">\n                    <td class=\"mail-checkbox\"><input type=\"checkbox\" name=\"message_"
    + alias3(((helper = (helper = helpers.message_id || (depth0 != null ? depth0.message_id : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"message_id","hash":{},"data":data}) : helper)))
    + "\"></td>\n                    <td class=\"mail-from\">"
    + alias3(((helper = (helper = helpers.senderText || (depth0 != null ? depth0.senderText : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"senderText","hash":{},"data":data}) : helper)))
    + "</td>\n                    <td class=\"mail-to\">"
    + alias3(((helper = (helper = helpers.toText || (depth0 != null ? depth0.toText : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"toText","hash":{},"data":data}) : helper)))
    + "</td>\n                    <td><a class=\"mail-link\" href=\"#"
    + alias3(((helper = (helper = helpers.message_id || (depth0 != null ? depth0.message_id : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"message_id","hash":{},"data":data}) : helper)))
    + "\">"
    + alias3(((helper = (helper = helpers.subjectText || (depth0 != null ? depth0.subjectText : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"subjectText","hash":{},"data":data}) : helper)))
    + "</a></td>\n                    <td class=\"mail-date\">"
    + alias3(((helper = (helper = helpers.sent_date || (depth0 != null ? depth0.sent_date : depth0)) != null ? helper : alias1),(typeof helper === alias2 ? helper.call(depth0,{"name":"sent_date","hash":{},"data":data}) : helper)))
    + "</td>\n                  </tr>\n";
},"useData":true});