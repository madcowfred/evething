# Bootstrap JS source files that we use
BOOTSTRAP_JS=static/js/bootstrap-alert.js static/js/bootstrap-button.js static/js/bootstrap-collapse.js static/js/bootstrap-dropdown.js \
	static/js/bootstrap-modal.js static/js/bootstrap-tooltip.js static/js/bootstrap-popover.js static/js/bootstrap-tab.js \
	static/js/bootstrap-scrollspy.js static/js/bootstrap-affix.js

BOOTSTRAP_FILES := alert button collapse dropdown modal tooltip popover tab scrollspy affix datepicker
BOOTSTRAP_JS := $(addsuffix .js,$(addprefix static/js/bootstrap-,$(BOOTSTRAP_FILES)))

# All JS source files that we use
ALL_JS := static/js/jquery.tablesorter.js static/js/bootstrap.js static/js/evething.js static/js/evething/*

# Themes
THEMES    := theme-cerulean theme-cosmo theme-cyborg theme-darkthing theme-default theme-slate
THEME_OUT := $(addprefix static/css/,$(addsuffix .min.css,$(THEMES)))

all : css js
css : $(THEME_OUT)
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

# Combine and minify all JS
static/js/evething-combined.min.js : $(ALL_JS)
	@echo -n Combining and minifying $(notdir $@)...
	@cat $(ALL_JS) > static/js/evething-combined.js
	@uglifyjs static/js/evething-combined.js --compress --mangle > static/js/evething-combined.min.js
	@echo \ done!

clean :
	rm -f static/js/bootstrap.js static/js/evething-combined.min.js
	rm -f $(THEME_OUT)
