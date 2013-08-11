# Bootstrap JS source files that we use
BOOTSTRAP_FILES := alert button collapse dropdown modal tooltip popover tab scrollspy affix datepicker
BOOTSTRAP_JS := $(addsuffix .js,$(addprefix static/js/bootstrap-,$(BOOTSTRAP_FILES)))

# All JS source files that we use
ALL_FILES := jquery.tablesorter.js jquery.cookie.js jquery.tablesorter.widgets.js bootstrap.js handlebars.runtime.js templates.js evething.js evething/*
ALL_JS    := $(addprefix static/js/,$(ALL_FILES))

# Themes
THEMES    := theme-cerulean theme-cosmo theme-cyborg theme-darkthing theme-default theme-slate
THEME_OUT := $(addprefix static/css/,$(addsuffix .min.css,$(THEMES)))

all : css handlebars js
css : $(THEME_OUT)
handlebars : static/js/templates.js
js  : static/js/bootstrap.js static/js/evething-combined.min.js

# Compile and minify LESS -> CSS
static/css/%.min.css : static/less/% static/less/bootstrap static/less/evething.less
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
	@cat $(ALL_JS) > static/js/evething-combined.js
	@uglifyjs static/js/evething-combined.js --compress --mangle > static/js/evething-combined.min.js
	@echo \ done!

clean :
	rm -f static/js/bootstrap.js static/js/templates.js static/js/evething-combined.min.js
	rm -f $(THEME_OUT)
