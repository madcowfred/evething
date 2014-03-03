(function() {
  var template = Handlebars.template, templates = Handlebars.templates = Handlebars.templates || {};
templates['home_character'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [4,'>= 1.0.0'];
helpers = this.merge(helpers, Handlebars.helpers); data = data || {};
  var buffer = "", stack1, helper, options, helperMissing=helpers.helperMissing, escapeExpression=this.escapeExpression, self=this, functionType="function";

function program1(depth0,data) {
  
  var buffer = "", stack1, helper, options;
  buffer += "\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    <div class=\"sensitive character-location";
  stack1 = helpers.unless.call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {hash:{},inverse:self.noop,fn:self.program(4, program4, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\">\n      <span class=\"location-hover\" rel=\"tooltip\" title=\""
    + escapeExpression((helper = helpers.systems_details || (depth0 && depth0.systems_details),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.last_known_location), options) : helperMissing.call(depth0, "systems_details", ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.last_known_location), options)))
    + "\">"
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.last_known_location)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</span>\n      ";
  stack1 = helpers['if'].call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.ship_item_id), {hash:{},inverse:self.noop,fn:self.program(6, program6, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    </div>\n    ";
  return buffer;
  }
function program2(depth0,data) {
  
  
  return "<hr>";
  }

function program4(depth0,data) {
  
  
  return " margin-half-top";
  }

function program6(depth0,data) {
  
  var buffer = "", stack1, helper, options;
  buffer += "\n      -- "
    + escapeExpression((helper = helpers.lookup || (depth0 && depth0.lookup),options={hash:{},data:data},helper ? helper.call(depth0, (depth0 && depth0.ships), ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.ship_item_id), options) : helperMissing.call(depth0, "lookup", (depth0 && depth0.ships), ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.ship_item_id), options)))
    + "\n      ";
  return buffer;
  }

function program8(depth0,data) {
  
  var buffer = "", stack1, helper, options;
  buffer += "\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {hash:{},inverse:self.noop,fn:self.program(2, program2, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    <div";
  stack1 = helpers.unless.call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {hash:{},inverse:self.noop,fn:self.program(9, program9, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += ">\n      <span class=\"skill-hover\" rel=\"popover\" title=\""
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" data-content=\"";
  stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.html)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1);
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\">"
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + " ";
  stack1 = helpers['if'].call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.to_level), {hash:{},inverse:self.noop,fn:self.program(11, program11, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "</span>\n      <span class=\"small\">(Rank "
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.skill)),stack1 == null || stack1 === false ? stack1 : stack1.rank)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + ")</span>\n      <br>\n      <em class=\"small skillduration\">"
    + escapeExpression((helper = helpers.shortduration || (depth0 && depth0.shortduration),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.duration), options) : helperMissing.call(depth0, "shortduration", ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.duration), options)))
    + " @ "
    + escapeExpression((helper = helpers.comma || (depth0 && depth0.comma),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.sp_per_hour), options) : helperMissing.call(depth0, "comma", ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.sp_per_hour), options)))
    + " SP/hr</em>\n      <em class=\"small pull-right queueduration\">Queue: "
    + escapeExpression((helper = helpers.shortduration || (depth0 && depth0.shortduration),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue_duration), options) : helperMissing.call(depth0, "shortduration", ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue_duration), options)))
    + "</em>\n      <div class=\"progress";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue_low), {hash:{},inverse:self.noop,fn:self.program(13, program13, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\">\n        <div class=\"bar\" style=\"width: "
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.complete_percent)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "%\">"
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.complete_percent)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "%</div>\n      </div>\n    </div>\n    ";
  return buffer;
  }
function program9(depth0,data) {
  
  
  return " class=\"margin-half-top\"";
  }

function program11(depth0,data) {
  
  var stack1, helper, options;
  return escapeExpression((helper = helpers.roman || (depth0 && depth0.roman),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.to_level), options) : helperMissing.call(depth0, "roman", ((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue)),stack1 == null || stack1 === false ? stack1 : stack1[0])),stack1 == null || stack1 === false ? stack1 : stack1.to_level), options)));
  }

function program13(depth0,data) {
  
  
  return " progress-danger";
  }

function program15(depth0,data) {
  
  
  return "<hr class=\"home-notifications hide\">";
  }

  buffer += "  <div class=\"well-small well home-character\">\n    <div>\n      <span class=\"large\">\n        <a href=\"character/"
    + escapeExpression(((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "\" class=\"sensitive character-name\" rel=\"tooltip\" title=\""
    + escapeExpression((helper = helpers.corp || (depth0 && depth0.corp),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.corporation), options) : helperMissing.call(depth0, "corp", ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.corporation), options)))
    + "\">"
    + escapeExpression(((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "</a>\n      </span>\n      <span class=\"small pull-right sensitive apikey-name\">["
    + escapeExpression(((stack1 = ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.apikey)),stack1 == null || stack1 === false ? stack1 : stack1.name)),typeof stack1 === functionType ? stack1.apply(depth0) : stack1))
    + "]</span>\n    </div>\n\n    <div>\n      <span>"
    + escapeExpression((helper = helpers.comma || (depth0 && depth0.comma),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.wallet_balance), options) : helperMissing.call(depth0, "comma", ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.wallet_balance), options)))
    + " ISK</span>\n      <span class=\"small pull-right total-sp\">"
    + escapeExpression((helper = helpers.comma || (depth0 && depth0.comma),options={hash:{},data:data},helper ? helper.call(depth0, ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.total_sp), options) : helperMissing.call(depth0, "comma", ((stack1 = ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.details)),stack1 == null || stack1 === false ? stack1 : stack1.total_sp), options)))
    + " SP</span>\n    </div>\n\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_LOCATIONS), {hash:{},inverse:self.noop,fn:self.program(1, program1, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.character)),stack1 == null || stack1 === false ? stack1 : stack1.skill_queue), {hash:{},inverse:self.noop,fn:self.program(8, program8, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    ";
  stack1 = helpers['if'].call(depth0, ((stack1 = (depth0 && depth0.profile)),stack1 == null || stack1 === false ? stack1 : stack1.HOME_SHOW_SEPARATORS), {hash:{},inverse:self.noop,fn:self.program(15, program15, data),data:data});
  if(stack1 || stack1 === 0) { buffer += stack1; }
  buffer += "\n    <ul class=\"home-notifications\">\n        <li class=\"no-game-time hide\"><i class=\"icon-time\" rel=\"tooltip\" title=\"Game time has expired!\"></i><span>Expired</span></li>\n        <li class=\"low-game-time hide\"><i class=\"icon-time\" rel=\"tooltip\" title=\"Remaining game time is low!\"></i><span></span></li>\n        <li class=\"key-expiring hide\"><i class=\"icon-key\" rel=\"tooltip\" title=\"API key is close to expiring!\"></i></li>\n        <li class=\"empty-skill-queue hide\"><i class=\"icon-list-ol\" rel=\"tooltip\" title=\"Skill queue is empty!\"></i><span>Empty!</span></li>\n        <li class=\"low-skill-queue hide\"><i class=\"icon-list-ol\" rel=\"tooltip\" title=\"Skill queue is not full!\"></i><span></span></li>\n        <li class=\"implants hide\"><i class=\"icon-lightbulb\" rel=\"tooltip\" title=\"Missing stat implants for currently training skill!\"></i><span></span></li>\n        <li class=\"clone hide\"><i class=\"icon-user-md\" rel=\"tooltip\" title=\"Insufficient clone!\"></i><span></span></li>\n    </ul>\n  </div>\n";
  return buffer;
  });
templates['mail_list'] = template(function (Handlebars,depth0,helpers,partials,data) {
  this.compilerInfo = [4,'>= 1.0.0'];
helpers = this.merge(helpers, Handlebars.helpers); data = data || {};
  var buffer = "", stack1, helper, functionType="function", escapeExpression=this.escapeExpression;


  buffer += "                  <tr";
  if (helper = helpers.rowClass) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.rowClass); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + " data-message-id=\"";
  if (helper = helpers.message_id) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.message_id); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + "\">\n                    <td class=\"mail-checkbox\"><input type=\"checkbox\" name=\"message_";
  if (helper = helpers.message_id) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.message_id); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + "\"></td>\n                    <td class=\"mail-from\">";
  if (helper = helpers.senderText) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.senderText); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + "</td>\n                    <td class=\"mail-to\">";
  if (helper = helpers.toText) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.toText); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + "</td>\n                    <td><a class=\"mail-link\" href=\"#";
  if (helper = helpers.message_id) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.message_id); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + "\">";
  if (helper = helpers.subjectText) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.subjectText); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + "</a></td>\n                    <td class=\"mail-date\">";
  if (helper = helpers.sent_date) { stack1 = helper.call(depth0, {hash:{},data:data}); }
  else { helper = (depth0 && depth0.sent_date); stack1 = typeof helper === functionType ? helper.call(depth0, {hash:{},data:data}) : helper; }
  buffer += escapeExpression(stack1)
    + "</td>\n                  </tr>\n";
  return buffer;
  });
})();