(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['mail_list'] = template({"compiler":[5,">= 2.0.0"],"main":function(depth0,helpers,partials,data) {
  var helper, functionType="function", escapeExpression=this.escapeExpression;
  return "                  <tr"
    + escapeExpression(((helper = helpers.rowClass || (depth0 && depth0.rowClass)),(typeof helper === functionType ? helper.call(depth0, {"name":"rowClass","hash":{},"data":data}) : helper)))
    + " data-message-id=\""
    + escapeExpression(((helper = helpers.message_id || (depth0 && depth0.message_id)),(typeof helper === functionType ? helper.call(depth0, {"name":"message_id","hash":{},"data":data}) : helper)))
    + "\">\n                    <td class=\"mail-checkbox\"><input type=\"checkbox\" name=\"message_"
    + escapeExpression(((helper = helpers.message_id || (depth0 && depth0.message_id)),(typeof helper === functionType ? helper.call(depth0, {"name":"message_id","hash":{},"data":data}) : helper)))
    + "\"></td>\n                    <td class=\"mail-from\">"
    + escapeExpression(((helper = helpers.senderText || (depth0 && depth0.senderText)),(typeof helper === functionType ? helper.call(depth0, {"name":"senderText","hash":{},"data":data}) : helper)))
    + "</td>\n                    <td class=\"mail-to\">"
    + escapeExpression(((helper = helpers.toText || (depth0 && depth0.toText)),(typeof helper === functionType ? helper.call(depth0, {"name":"toText","hash":{},"data":data}) : helper)))
    + "</td>\n                    <td><a class=\"mail-link\" href=\"#"
    + escapeExpression(((helper = helpers.message_id || (depth0 && depth0.message_id)),(typeof helper === functionType ? helper.call(depth0, {"name":"message_id","hash":{},"data":data}) : helper)))
    + "\">"
    + escapeExpression(((helper = helpers.subjectText || (depth0 && depth0.subjectText)),(typeof helper === functionType ? helper.call(depth0, {"name":"subjectText","hash":{},"data":data}) : helper)))
    + "</a></td>\n                    <td class=\"mail-date\">"
    + escapeExpression(((helper = helpers.sent_date || (depth0 && depth0.sent_date)),(typeof helper === functionType ? helper.call(depth0, {"name":"sent_date","hash":{},"data":data}) : helper)))
    + "</td>\n                  </tr>\n";
},"useData":true});
})();