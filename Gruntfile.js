module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    handlebars: {
      hanldbears: {
        options: {
          namespace: 'Handlebars.templates',
          processName: function (filePath) {
              return filePath.replace(/^static\/handlebars\//, '').replace(/\.handlebars$/, '');
          }
        },
        files: {
          'static/js/templates.js': 'static/handlebars/*.handlebars'
        }
      }
    },
    uglify: {
      combined: {
        options: {
          sourceMap: true
        },
        src: [
          'static/js/jquery.tablesorter.js',
          'static/js/jquery.tablesorter.widgets.js',
          'static/js/bootstrap-alert.js',
          'static/js/bootstrap-button.js',
          'static/js/bootstrap-collapse.js',
          'static/js/bootstrap-dropdown.js',
          'static/js/bootstrap-modal.js',
          'static/js/bootstrap-tooltip.js',
          'static/js/bootstrap-popover.js',
          'static/js/bootstrap-tab.js',
          'static/js/bootstrap-scrollspy.js',
          'static/js/bootstrap-affix.js',
          'static/js/bootstrap-datepicker.js',
          'static/js/handlebars.runtime.js',
          'static/js/templates.js',
          'static/js/evething.js',
          'static/js/evething/*.js'
        ],
        dest: 'static/js/evething-combined.min.js'
      }
    },
    less: {
      options: {
        cleancss: true
      },
      themes: {
        files: {
          'static/css/theme-cerulean.min.css': 'static/less/theme-cerulean/bootstrap.less',
          'static/css/theme-cosmo.min.css': 'static/less/theme-cosmo/bootstrap.less',
          'static/css/theme-cyborg.min.css': 'static/less/theme-cyborg/bootstrap.less',
          'static/css/theme-darkthing.min.css': 'static/less/theme-darkthing/bootstrap.less',
          'static/css/theme-default.min.css': 'static/less/theme-default/bootstrap.less',
          'static/css/theme-slate.min.css': 'static/less/theme-slate/bootstrap.less'
        }
      }
    }
  });

  grunt.loadNpmTasks('grunt-contrib-handlebars');
  grunt.loadNpmTasks('grunt-contrib-uglify');
  grunt.loadNpmTasks('grunt-contrib-less');

  // Default task(s).
  grunt.registerTask('default', ['handlebars', 'uglify', 'less']);
};
