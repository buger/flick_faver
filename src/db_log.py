from google.appengine.api import apiproxy_stub_map
from google.appengine.api import memcache
from google.appengine.datastore import datastore_index
import logging
import operator


def db_log(model, call, details=''):
  """Call this method whenever the database is invoked.
  
  Args:
    model: the model name (aka kind) that the operation is on
    call: the kind of operation (Get/Put/...)
    details: any text that should be added to the detailed log entry.
  """
  
  # First, let's update memcache
  if model:
    stats = memcache.get('DB_TMP_STATS')
    if stats is None: stats = {}
    key = '%s_%s' % (call, model)
    stats[key] = stats.get(key, 0) + 1
    memcache.set('DB_TMP_STATS', stats)
  
  # Next, let's log for some more detailed analysis
  logging.debug('DB_LOG: %s @ %s (%s)', call, model, details)

def patch_appengine():
    def hook(service, call, request, response):
        logging.info('%s %s - %s' % (service, call, str(request)))

    apiproxy_stub_map.apiproxy.GetPreCallHooks().Append('db_log', hook, 'datastore_v3')      