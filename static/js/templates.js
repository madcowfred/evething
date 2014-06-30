(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['home_character'] = template({"1":function(depth0,helpers,partials,data) {
  var stack1, helper, helperMissing=helpers.helperMissing, escapeExpression=this.escapeExpression, functionType="function", buffer = "\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {"name":"if","hash":{},"fn":this.program(2, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    <div class=\"sensitive character-location";
  stack1 = helpers.unless.call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {"name":"unless","hash":{},"fn":this.program(4, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\">\n      <span class=\"location-hover\" rel=\"tooltip\" title=\""
    + escapeExpression((helper = helpers.systems_details || (depth0 && depth0.systems_details) || helperMissing,helper.call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.last_known_location), {"name":"systems_details","hash":{},"data":data})))
    + "\">"
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.last_known_location)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</span>\n      ";
  stack1 = helpers['if'].call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.ship_item_id), {"name":"if","hash":{},"fn":this.program(6, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  return buffer + "\n    </div>\n    ";
},"2":function(depth0,helpers,partials,data) {
  return "<hr>";
  },"4":function(depth0,helpers,partials,data) {
  return " margin-half-top";
  },"6":function(depth0,helpers,partials,data) {
  var stack1, escapeExpression=this.escapeExpression;
  return "\n      -- "
    + escapeExpression(helpers.lookup.call(depth0, (depth0 && depth0.ships), ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.ship_item_id), {"name":"lookup","hash":{},"data":data}))
    + "\n      ";
},"8":function(depth0,helpers,partials,data) {
  var stack1, helper, functionType="function", escapeExpression=this.escapeExpression, helperMissing=helpers.helperMissing, buffer = "\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {"name":"if","hash":{},"fn":this.program(2, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    <div";
  stack1 = helpers.unless.call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {"name":"unless","hash":{},"fn":this.program(9, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += ">\n      <span class=\"skill-hover\" rel=\"popover\" title=\""
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" data-content=\"";
  stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.html)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1);
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\">"
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + " ";
  stack1 = helpers['if'].call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.to_level), {"name":"if","hash":{},"fn":this.program(11, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "</span>\n      <span class=\"small\">(Rank "
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.rank)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + ")</span>\n      <br>\n      <em class=\"small skillduration\">"
    + escapeExpression((helper = helpers.shortduration || (depth0 && depth0.shortduration) || helperMissing,helper.call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.duration), {"name":"shortduration","hash":{},"data":data})))
    + " @ "
    + escapeExpression((helper = helpers.comma || (depth0 && depth0.comma) || helperMissing,helper.call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.sp_per_hour), {"name":"comma","hash":{},"data":data})))
    + " SP/hr</em>\n      <em class=\"small pull-right queueduration\">Queue: "
    + escapeExpression((helper = helpers.shortduration || (depth0 && depth0.shortduration) || helperMissing,helper.call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue_duration), {"name":"shortduration","hash":{},"data":data})))
    + "</em>\n      <div class=\"progress";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue_low), {"name":"if","hash":{},"fn":this.program(13, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  return buffer + "\">\n        <div class=\"bar\" style=\"width: "
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.complete_percent)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "%\">"
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.complete_percent)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "%</div>\n      </div>\n    </div>\n    ";
},"9":function(depth0,helpers,partials,data) {
  return " class=\"margin-half-top\"";
  },"11":function(depth0,helpers,partials,data) {
  var stack1, helper, helperMissing=helpers.helperMissing, escapeExpression=this.escapeExpression;
  return escapeExpression((helper = helpers.roman || (depth0 && depth0.roman) || helperMissing,helper.call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1['0'])),stack1 == null || stack1 === false ? stack1 : stack1.to_level), {"name":"roman","hash":{},"data":data})));
  },"13":function(depth0,helpers,partials,data) {
  return " progress-danger";
  },"15":function(depth0,helpers,partials,data) {
  return "<hr class=\"home-notifications hide\">";
  },"compiler":[5,">= 2.0.0"],"main":function(depth0,helpers,partials,data) {
  var stack1, helper, functionType="function", escapeExpression=this.escapeExpression, helperMissing=helpers.helperMissing, buffer = "  <div class=\"well-small well home-character\">\n    <div>\n      <span class=\"large\">\n        <a href=\"character/"
    + escapeExpression(((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" class=\"sensitive character-name\" rel=\"tooltip\" title=\""
    + escapeExpression((helper = helpers.corp || (depth0 && depth0.corp) || helperMissing,helper.call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.corporation), {"name":"corp","hash":{},"data":data})))
    + "\">"
    + escapeExpression(((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</a>\n      </span>\n      <span class=\"small pull-right sensitive apikey-name\">["
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.apikey)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "]</span>\n    </div>\n\n    <div>\n      <span>"
    + escapeExpression((helper = helpers.comma || (depth0 && depth0.comma) || helperMissing,helper.call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.wallet_balance), {"name":"comma","hash":{},"data":data})))
    + " ISK</span>\n      <span class=\"small pull-right total-sp\">"
    + escapeExpression((helper = helpers.comma || (depth0 && depth0.comma) || helperMissing,helper.call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.total_sp), {"name":"comma","hash":{},"data":data})))
    + " SP</span>\n    </div>\n\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_LOCATIONS), {"name":"if","hash":{},"fn":this.program(1, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue), {"name":"if","hash":{},"fn":this.program(8, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {"name":"if","hash":{},"fn":this.program(15, data),"inverse":this.noop,"data":data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  return buffer + "\n    <ul class=\"home-notifications\">\n        <li class=\"no-game-time hide\"><i class=\"icon-time\" rel=\"tooltip\" title=\"Game time has expired!\"></i><span>Expired</span></li>\n        <li class=\"low-game-time hide\"><i class=\"icon-time\" rel=\"tooltip\" title=\"Remaining game time is low!\"></i><span></span></li>\n        <li class=\"key-expiring hide\"><i class=\"icon-key\" rel=\"tooltip\" title=\"API key is close to expiring!\"></i></li>\n        <li class=\"empty-skill-queue hide\"><i class=\"icon-list-ol\" rel=\"tooltip\" title=\"Skill queue is empty!\"></i><span>Empty!</span></li>\n        <li class=\"low-skill-queue hide\"><i class=\"icon-list-ol\" rel=\"tooltip\" title=\"Skill queue is not full!\"></i><span></span></li>\n        <li class=\"implants hide\"><i class=\"icon-lightbulb\" rel=\"tooltip\" title=\"Missing stat implants for currently training skill!\"></i><span></span></li>\n        <li class=\"clone hide\"><i class=\"icon-user-md\" rel=\"tooltip\" title=\"Insufficient clone!\"></i><span></span></li>\n    </ul>\n  </div>\n";
},"useData":true});
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