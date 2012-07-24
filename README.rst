========
EVEthing
========

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

- Only crashes occasionally, honest.

- More than likely won't set your hard drive on fire.

- Home page: displays relevant information about all API keys related to your account.
  `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/home.png>`_.
  
  + Character name, wallet balance, API key 'name' (in brackets) and total SP easily
    visible.
  + If the account is training, shows training skill, time remaining and training
    speed. Red completion bars have free room in the skill queue.
  + Notification icons appear at the bottom of each character box and have basic
    tooltips, you can see the current types in the example screenshot.
  + Red boxes highlight accounts with no characters in training.
  + Wallet balances for any corporation keys are displayed underneath.

- Character page: displays character information similar to the in-game character sheet.
  If you've ever used `eveboard <http://eveboard.com>`_ you should know what to expect.
  `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/character.png>`_
  (yes, that's me).

  + Basic info: portrait, corporation, wallet balance, total SP, clone limit, attributes and
    implants.
  + Skill queue.
  + Filled stars for trained levels, hollow stars for partially trained levels, weird heart icons for
    level V skills.
  + Full control over public visibility of character and of each component. If you're not
    logged in to the account that owns a character you will only see what the owner says
    you can see, or a 404 error if they choose to not be public.
  + Anonymous character support, accessed via a /character_anon/blah URL. Character name,
    corporation, wallet balance and implants are not shown and your portrait is replaced
    with a placeholder.

- API key management page: list keys, add keys, simple interface to generate a new key with
  a feature set. `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/apikeys.png>`_

- Assets page: lists assets for all characters with the relevant API mask. Includes ship
  and container names with the Locations mask. Filtering is somewhat limited and search is
  non-existent but the basic functionality is in and working.
  `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/assets.png>`_

- Blueprints page: lets you add/delete/edit/view blueprints you have added to the system.
  `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/blueprints.png>`_
  
  + See useful information at a glance for every blueprint you own (assume you could be
    bothered entering them all).
  + Mark a selection of blueprints to use with BPCalc.

- BPCalc page: displays detailed production information and allows you to filter based on
  things. `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/bpcalc.png>`_

  + Displays blueprints, total m3 of inputs/ouputs, expected profit values from both buys
    and sells, and estimated weekly volume.
  + Not particularly powerful filters on the data:
    - Profit below a certain value
    - Movement above a certain value (so you don't make 300% of the weekly supply)
    - Limit slots to a certain value
    - Remove selected blueprints
  + Components table with IGB-clickable links for easy purchasing of items.

- Orders page: displays a summary of your market orders and a detailed table.
  `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/orders.png>`_

  + Summary table showing active order slots and total values involved.
  + Detailed active orders table listing all relevant information for each order, with
    clickable item names that lead to Transactions pages.

- Transactions page: displays a log of market transactions for all items or a specific
  item. `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/transactions.png>`_

  + All transactions page has clickable item links that lead to specific items.

- Trade page: displays a summary of all transactions by month and over specific 'Campaigns'.
  `Screenshot <https://github.com/madcowfred/evething/raw/develop/doc-images/trade.png>`_
   

Future Plans
============

- Take over the universe.

Installation
============

There are some common requirements for any install method, you will need:

- `Python <http://www.python.org>`_ >=2.7 <3.0
- `Django <http://www.djangoproject.com>`_ >=1.4
- `Django MPTT <https://github.com/django-mptt/django-mptt/>`_ >=0.5
- `South <http://south.aeracode.org/>`_ >=0.7
- `Coffin <https://github.com/coffin/coffin/>`_ >=0.3
- `Jinja2 <http://jinja.pocoo.org/>`_ >=2.6
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
don't want to use this as a real site due to issues (TODO: link to the Django page about
this).

#. Make sure you have Python 2.7+ and Django 1.4+ installed.
#. Extract the EVEthing stuff somewhere.
#. Copy evething/local_settings.example to evething/local_settings.py then open
   evething/local_settings.py in some sort of text editor and edit stuff. 'sqlite' is
   included with Python and is generally the easiest database to set up.
#. ``python manage.py syncdb``, say yes when it asks if you want an admin user.
#. ``python manage.py migrate thing 0001 --fake`` (South is weird).
#. ``python manage.py runserver``.
#. Open http://localhost:8000/ in whatever browser you use.
#. Log in as the admin user you created earlier.
#. Click the cog in the top right then 'API keys'.
#. Add one or more API keys.
#. ``python api_updater.py`` and wait while it pulls a huge pile of information.

If you update EVEthing in the future, make sure you run ``python manage.py migrate thing``
to apply any database schema changes!

Hosted Install
--------------
#. TODO: Apache + mod_wsgi information.
#. TODO: nginx + uwsgi/gunicorn information.
