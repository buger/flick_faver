from google.appengine.ext import db
from google.appengine.tools import bulkloader
import datetime

class User(db.Model):
    username  = db.StringProperty()        
    fullname  = db.StringProperty()
    icon_url  = db.LinkProperty()

    token     = db.StringProperty()

    status    = db.IntegerProperty(default = 200)
    
    state = db.IntegerProperty(default = 400)
    
    difficulty = db.IntegerProperty(default = 100)
    layout     = db.IntegerProperty(default = 501)

    updated  = db.DateTimeProperty()                 
    created  = db.DateTimeProperty(auto_now_add = True)
        
    last_login = db.DateTimeProperty()
    

class UserLoader(bulkloader.Loader):
    def __init__(self):
        bulkloader.Loader.__init__(self, 'User',
                                     [
                                      ('username', str),
                                      ('last_login', lambda x: datetime.datetime.fromtimestamp(float(x))),
                                      ('created', lambda x: datetime.datetime.fromtimestamp(float(x)))
                                     ])
            
    def generate_key(self, i, values):
        return values[0]

loaders = [UserLoader]