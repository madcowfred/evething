========
EVEthing
========

EVEthing is a terribly named web application intended to ease the pain of managing your
EVE space empire.

- Written entirely in Python
- Uses the Django web development framework with django-mptt to store and handle hierarchical
  data.
- Uses the excellent `Twitter Bootstrap <http://twitter.github.com/bootstrap/>`_ CSS framework.

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
- Skill plan creation.
- Wallet Journal tracking.
- Contract tracking.
- Industry Job tracking.
- CREST integration once CCP actually releases something.

Installation
============

There are some common requirements for any install method, you will need:

- `Python <http://www.python.org>`_ >=2.7 <3.0
- `Django <http://www.djangoproject.com>`_ >=1.4
- `Django MPTT <https://github.com/django-mptt/django-mptt/>`_ >=0.5
- `South <http://south.aeracode.org/>`_ >=0.7
- `Coffin <https://github.com/coffin/coffin/>`_ >=0.3
- `Jinja2 <http://jinja.pocoo.org/>`_ >=2.6
- The current EVE database dump (SQLite format) from `here <http://zofu.no-ip.de/>`_.
- A database server and client library.
  + `SQLite <http://www.sqlite.org>`_ is the simplest and is often included with Python.
  + `MySQL <http://www.mysql.com>`_ is another option and highly likely to be available on
    shared hosting. You will need the `MySQLdb <http://mysql-python.sourceforge.net/MySQLdb.html>`_
    client library.
  + `PostgreSQL <http://www.postgresql.org>`_ is the last option and would be my choice.
    You will need the `psycopg <http://initd.org/psycopg/>`_ client library.

Common Install Steps
--------------------
#. Extract the EVEthing stuff somewhere.
#. Copy evething/local_settings.example to evething/local_settings.py then open
   evething/local_settings.py in some sort of text editor and edit setings.
#. ``python manage.py syncdb``, say yes and fill in useful information when it asks if you
   would like to create an admin user.
#. ``python manage.py migrate thing --fake`` (so South knows what state the database is
   in for future migrations).
#. ``python import.py`` to import the initial data from the database dump.

If you update EVEthing in the future, make sure you run ``python manage.py migrate thing``
to apply any database schema changes!

Common Post-install Steps
-------------------------
#. Log in as the admin user you created earlier.
#. Click the username dropdown in the top right and head to Account Management.
#. Add one or more API keys.
#. ``python api_updater.py`` and wait while it pulls a huge pile of information.

Local Install
-------------
This is for messing about with EVEthing and seeing what the hell it does, never use this for a
publicly accessible site (see: `Django docs <https://docs.djangoproject.com/en/dev/ref/django-admin/#runserver-port-or-address-port>`_).

#. ``python manage.py runserver``.
#. Open http://localhost:8000/ in a web browser.

Apache Install
--------------
You will need to install Apache and `mod_wsgi <http://code.google.com/p/modwsgi/>`_.

#. Make a directory somewhere to act as the site root (and possibly contain static files).
   Do NOT use the same directory you placed the EVEthing files earlier.
#. Add a vhost to your Apache config with these extra directives:::

   Alias /static/ /www/whatever/static/

   <Directory /www/whatever>
       Order allow,deny
       Allow from all
   </DIrectory>

   WSGIDaemonProcess evething threads=2 user=nobody
   WSGIProcessGroup evething

   WSGIScriptAlias / /path/to/evething/wsgi.py

   <Directory /path/to/evething>
       <Files wsgi.py>
           Order allow,deny
           Allow from all
       </Files>
   </Directory>

#. Reload Apache config.
#. Open http://whatever/ in a web browser.
#. To force an EVEthing reload later (updated code or changed config) simply ``touch wsgi.py``
   in the EVEthing directory.
