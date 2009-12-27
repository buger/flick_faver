'''
Created on 04.12.2009

@author: buger
'''
from google.appengine.ext import db
from google.appengine.api.labs import taskqueue        

import const
import flickr

class User(db.Model):
    username  = db.StringProperty()        
    fullname  = db.StringProperty(indexed = False)
    icon_url  = db.LinkProperty(indexed = False)

    token     = db.StringProperty(indexed = False)

    status    = db.IntegerProperty(choices = set(const.UserStatuses), 
                                   default = const.UserUnRegistred)
    
    difficulty = db.IntegerProperty(default = const.SkillLevelHard, indexed = False)
    layout     = db.IntegerProperty(choices = set(const.Layouts), 
                                    default = const.LayoutMedium, indexed = False)
    
    latest_photo = db.StringProperty(indexed = False)
    
    updated  = db.DateTimeProperty()                 
    created  = db.DateTimeProperty(auto_now_add = True)
        
    last_login = db.DateTimeProperty()
    
    @property
    def nsid(self):
        return self.key().name()
    
    def update_subscribers(self, initial_update = None):
        subscribers = UserContact.all()
                
        subscribers.filter("contact", self.key().name())
        subscribers = subscribers.fetch(20)
        
        for subscriber in subscribers:
            self.update_subscriber(subscriber.user, initial_update)
               
    def update_subscriber(self, subscriber, initial_update = None):
        task = taskqueue.Task(url="/task/user/update_subscriber_index",                              
                              params={'key': self.key(), 
                                      'subscriber': db.Key.from_path('User', subscriber),
                                      'initial_update': initial_update}, 
                              method = 'POST')
        
        if initial_update is None:
            task.add("update-photos")
        else:   
            task.add("non-blocking")
                        
    @classmethod
    def new_from_xml(cls, user_xml):
        nsid = user_xml.getAttribute('nsid')        
        
        icon_server = user_xml.getAttribute('iconserver')
        icon_farm = user_xml.getAttribute('iconfarm')
        username = user_xml.getAttribute('username')
                            
        return User(key_name = nsid,
                    nsid     = nsid,
                    username = username,                
                    icon_url = flickr.icon_url(farm = icon_farm, server = icon_server, nsid = nsid),
                    status = const.UserUnRegistred)                       
    
# Ancestor is User
class UserContact(db.Model):
    user    = db.StringProperty()
    contact = db.StringProperty() 
        
    friend  = db.BooleanProperty(default = False)
    family  = db.BooleanProperty(default = False)
    
    show_photos    = db.BooleanProperty(default = True)
    show_favorites = db.BooleanProperty(default = True)     
    
    updated = db.DateTimeProperty()                          