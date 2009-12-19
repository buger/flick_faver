from google.appengine.ext import db
from google.appengine.tools import bulkloader
import time

class User(db.Model):
    username  = db.StringProperty(required = True)
    userid    = db.StringProperty(required = True)
    fullname  = db.StringProperty()
    
    last_login = db.DateTimeProperty()
    updated_at = db.DateTimeProperty() # Last favorites update 
    created_at = db.DateTimeProperty(auto_now_add = True)
    
    processing_state = db.IntegerProperty()

class UserExporter(bulkloader.Exporter):
    def __init__(self):
        bulkloader.Exporter.__init__(self, 'User',
                                     [
                                      ('userid', str, None),                                      
                                      ('last_login', lambda x: time.mktime(x.timetuple()) , None),
                                      ('created_at', lambda x: time.mktime(x.timetuple()), None)
                                     ])        

exporters = [UserExporter]