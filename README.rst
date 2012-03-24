========
EVEthing
========

EVEthing is a terrible named web application intended to ease the pain of manging
your EVE space empire. It is written in Python using the Django framework.

Features
========

- Home page: displays relevant information about all API keys related to your
  account - `example <http://wafflemonster.org/freddie/evething/home.png>`_. Blue
  bars are training, red bars have free room in the skill queue, little profile icon
  is a tooltip for inadequate clone, little clock icon is a tooltip for <10d game time
  remaining. Accounts that are not training have red background boxes (not shown).

- Character page: displays character information (picture, name, wallet balance,
  attributes, implants, training queue, skill list), quite similar to `eveboard
  <http://eveboard.com>`_. There are options to control the public visibility of this
  information, defaulting to False.  TODO: add screenshots.

Local Install
=============
This is for messing about with EVEthing and seeing what the hell it does, do not
use this as a production site.

#. Make sure you have Python 2.7.x and Django whatever-is-stable installed.

#. Extract the EVEthing stuff somewhere.

#. Copy local_settings.example to local_settings.py, then open local_settings.py
   in some sort of text editor and edit stuff. 'sqlite' is included with Python
   and will work, use that for the database setup.
#. Run ``python manage.py syncdb``, say yes when it asks if you want an admin user.
#. Run ``python manage.py runserver``.
#. Open http://localhost:8000/ in whatever browser you use.
#. Log in as the admin user you created earlier.
#. Click the cog in the top right then 'API keys'.
#. Add one or more API keys.
#. Run ``python api_updater.py`` and wait while it pulls a huge pile of information.

Hosting Install
===============
#. Ughhhhh. This is non-trivial, deploying a Python web app is awful.
