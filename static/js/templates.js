(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['mail_list'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [4,'>= 1.0.0'];
helpers = this.merge(helpers, Handlebars.helpers); data = data || {};
  var buffer = "", stack1, functionType="function", escapeExpression=this.escapeExpression;


  buffer += "                  <tr";
  if (stack1 = helpers.rowClass) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.rowClass; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + ">\n                    <td class=\"mail-checkbox\"><input type=\"checkbox\"></td>\n                    <td class=\"mail-from\">";
  if (stack1 = helpers.senderText) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.senderText; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</td>\n                    <td class=\"mail-to\">";
  if (stack1 = helpers.toText) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.toText; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</td>\n                    <td><a class=\"mail-link\" href=\"#";
  if (stack1 = helpers.message_id) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.message_id; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "\">";
  if (stack1 = helpers.subjectText) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.subjectText; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</a></td>\n                    <td class=\"mail-date\">";
  if (stack1 = helpers.sent_date) { stack1 = stack1.call(depth0, {hash:{},data:data}); }
  else { stack1 = depth0.sent_date; stack1 = typeof stack1 === functionType ? stack1.apply(depth0) : stack1; }
  buffer += escapeExpression(stack1)
    + "</td>\n                  </tr>\n";
  return buffer;
  });
})();