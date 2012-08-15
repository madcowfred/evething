========
EVEthing
========

USE THE DEVELOP TREE.
USE THE DEVELOP TREE.
USE THE DEVELOP TREE.
USE THE DEVELOP TREE.
USE THE DEVELOP TREE.

(this tree won't be updated until an actual release occurs, good luck with that)

EVEthing is a terribly named web application intended to ease the pain of managing your
EVE space empire.

- Written entirely in Python
- Uses the Django web development framework, with django-mptt to store and handle hierarchical
  data.
- Uses the excellent `Twitter Bootstrap <http://twitter.github.com/bootstrap/>`_ layout framework.
  With an almost default theme because colours are hard.

Features
========

- Handles all types of API key: account, character and corporation.

- Only crashes occasionally, honest. More than likely will not set your hard drive on fire.

- Home page: displays relevant information about all API keys related to your account.
  `Screenshot <https://github.com/madcowfred/evething/raw/master/doc-images/home.png>`_.
  
  + Character name, wallet balance, API key 'name' (in brackets) and total SP easily
    visible.
  + If the account is training, shows training skill, time remaining and training
    speed. Red completion bars have free room in the skill queue.
  + Notification icons appear at the bottom of each character box and have basic
    tooltips, you can see the current types in the example screenshot.
  + Red boxes highlight accounts with no characters in training.

- Character page: displays character information similay to the in-game character sheet.
  If you've ever used `eveboard <http://eveboard.com>`_ you should know what to expect.
  `Screenshot <https://github.com/madcowfred/evething/raw/master/doc-images/character.png>`_
  (yes, that's my character).

  + Basic info: portrait, corporation, wallet balance, total SP, clone limit, attributes and
    implants.
  + Skill queue.
  + Weird heart icons for level V skills.
  + Full control over public visibility of character and of each component. If you're not
    logged in to the account that owns a character you will only see what the owner says
    you can see, or a 404 error if they choose to not be public.
  + Anonymous character support, accessed via a /character_anon/blah URL. Character name
    is not shown, portrait is replaced with a placeholder.

- API key management page: list keys, add keys, simple interface to generate a new key with
  a feature set. `Screenshot <https://github.com/madcowfred/evething/raw/master/doc-images/apikeys.png>`_

- Assets page: lists assets for all characters with the relevant API mask. Includes ship
  and container names with the Locations mask. Filtering is somewhat limited and search is
  non-existent but the basic functionality is in and working.
  `Screenshot <https://github.com/madcowfred/evething/raw/master/doc-images/assets.png>`_

Future Plans
============

- Take over the universe.

Installation
============

There are some common requirements for any install method, you will need:

- `Python <http://www.python.org>`_ 2.6+, NOT 3.x
- `Django <http://www.djangoproject.com>`_ 1.4+
- `Django MPTT <https://github.com/django-mptt/django-mptt/>`_ 0.5+
- A database server and client library.
  
  + `SQLite <http://www.sqlite.org>`_ is the simplest and is often included with Python.
  + `MySQL <http://www.mysql.com>`_ is another option and highly likely to be available on
    shared hosting. You will need the `MySQLdb <http://mysql-python.sourceforge.net/MySQLdb.html>`_
    client library.
  + `PostgreSQL <http://www.postgresql.org>`_ is the last option and would be my choice.
    You will need the `psycopg <http://initd.org/psycopg/>`_ client library.

Local Install
-------------
This is for messing about with EVEthing and seeing what the hell it does, you probably
shouldn't use this as a production site.

#. Make sure you have Python 2.6+ and Django 1.4+ installed.
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

Hosted Install
--------------
#. Put some Apache + mod_wsgi stuff here for the easy option.
#. Put some nginx + uwsgi/gunicorn stuff here to scare people away.
