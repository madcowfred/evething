# Bootstrap JS source files that we use
BOOTSTRAP_FILES := alert button collapse dropdown modal tooltip popover tab scrollspy affix datepicker
BOOTSTRAP_JS := $(addsuffix .js,$(addprefix static/js/bootstrap-,$(BOOTSTRAP_FILES)))

# All JS source files that we use
ALL_FILES := jquery.tablesorter.js jquery.tablesorter.widgets.js jquery.cookie.js bootstrap.js requestAnimationFrame.polyfill.js handlebars.runtime.js templates.js evething.js evething/*
ALL_JS    := $(addprefix static/js/,$(ALL_FILES))

# Themes
THEMES    := theme-cerulean theme-cosmo theme-cyborg theme-darkthing theme-default theme-slate
THEME_OUT := $(addprefix static/css/,$(addsuffix .min.css,$(THEMES)))

all : css handlebars js
css : $(THEME_OUT)
handlebars : static/js/templates.js
js  : static/js/bootstrap.js static/js/evething-combined.min.js static/js/evething-combined.min.js.map

# Compile and minify LESS -> CSS
static/css/%.min.css : static/less/%/ static/less/bootstrap/ static/less/evething.less static/less/evething/
	@echo -n Compiling and minifying $(notdir $@)...
	@recess --compress $</bootstrap.less > $@
	@echo \ done!

# Pre-combine bootstrap JS
static/js/bootstrap.js : $(BOOTSTRAP_JS)
	@echo -n Combining Bootstrap JS source files...
	@cat $(BOOTSTRAP_JS) > static/js/bootstrap.js
	@echo \ done!

# Handlebars
static/js/templates.js : static/handlebars/*.handlebars
	@echo -n Compiling templates...
	@handlebars static/handlebars/*.handlebars -f $@
	@echo \ done!

# Combine and minify all JS
static/js/evething-combined.min.js : $(ALL_JS)
	@echo -n Combining and minifying $(notdir $@)...
	@uglifyjs $(ALL_JS) --source-map static/js/evething-combined.min.js.map --output static/js/evething-combined.min.js --source-map-root=../../ --source-map-url=/static/js/evething-combined.min.js.map --compile --mangle 
	@echo \ done!

clean :
	rm -f static/js/bootstrap.js static/js/templates.js static/js/evething-combined.min.js static/js/evething-combined.min.js.map
	rm -f $(THEME_OUT)
