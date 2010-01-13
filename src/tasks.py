import logging
import datetime
import time
import itertools

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db
from google.appengine.ext import deferred


import flickr
import const

from models.user import *
from models.photo import *
from models.subscription import *


class UpdateContactsHandler(webapp.RequestHandler):
    def post(self):
        user_key = self.request.get('key')        
        user     = User.get(user_key)
        
        if self.request.get('initial_update') is not None:
            initial_update = True
            countdown = 0
        else:
            initial_update = False
            countdown = 60
        
        if user:
            try:
                page = int(self.request.get('page'))
            except ValueError:
                page = 1
                
            objects_to_put = []
            
            contacts_xml, max_pages = flickr.get_contacts(user.nsid, page)                                 
            
            logging.info("Contact pages %s, user: %s" % (max_pages, user.nsid))
            logging.info("Contacts len %s" % len(contacts_xml))
            
            tasks = []
                                                                
            for contact_xml in contacts_xml:                
                contact_nsid = contact_xml.getAttribute('nsid')            
                contact = User.get_by_key_name(contact_nsid)
                
                if contact is None:
                    contact = User.new_from_xml(contact_xml)                    
                    
                    objects_to_put.append(contact)
                                                                                  
                    task = taskqueue.Task(url="/task/user/update_favorites",
                                          countdown = countdown,                                          
                                          params={'key': contact.key(),                                      
                                                  'initial_update': initial_update, 
                                                  'photos-per-contact': 5})
                              
                    tasks.append(task)
                                                                                                                                                                                     
                user_contact = UserContact.get_by_key_name(contact_nsid, user)
                                
                if user_contact is None:
                    ignored = int(contact_xml.getAttribute('ignored')) == 1
                                    
                    user_contact = UserContact(key_name = contact_nsid,
                                               parent  = user,
                                               user = user.key().name(),
                                               contact = contact.key().name(),                                          
                                               show_photos = not ignored,
                                               show_favorites = not ignored)
                                    
                    objects_to_put.append(user_contact)
                    
                    if contact.is_saved():
                        task = taskqueue.Task(url="/task/user/update_subscriber_index",
                                              countdown = countdown,                              
                                              params={'key': contact.key(), 
                                                      'subscriber': user.key(),
                                                      'initial_update': initial_update})
                    
                        tasks.append(task)                                                            
            
            db.put(objects_to_put)
            
            for task in tasks:
                if self.request.get('initial_update') is None:
                    task.add('update-photos')
                else:
                    task.add('non-blocking')
                                                                    
            if page <= max_pages:
                page = page + 1

                taskqueue.Task(url="/task/user/update_contacts",
                               countdown = countdown, 
                               params={'key':user_key, 
                                       'initial_update': initial_update, 
                                       'page': page}).add("update-contacts")
        else:
            self.response.out.write("Unknown user")
            logging.error("Can't update contacts. Unknown user %s" % user_key)
            
            
    def get(self):
        self.post()


class UpdateFavesHandler(webapp.RequestHandler):
    def post(self):
        if self.request.get('photos-per-contact'):
            photos_per_contact = int(self.request.get('photos-per-contact'))
        else:
            photos_per_contact = flickr.PHOTOS_PER_CONTACT
            
        user_key = self.request.get('key')            
        user = User.get(user_key)                                
                        
        six_hours_ago = datetime.datetime.now()-datetime.timedelta(minutes=360)
        
        if user.updated is not None and user.updated > six_hours_ago:
            # It's up to date, updating only subscriber indexes
            user.update_subscribers(self.request.get('initial_update'))   
        else:   
            objects_to_put = []
            counter = 0
                            
            user.updated = datetime.datetime.now()
                
            photos_xml = flickr.get_faves(user.nsid, photos_per_contact)
                                        
            for photo_xml in photos_xml:
                photo_id = photo_xml.getAttribute('id')
                
                if len(photo_id) == 0:
                    continue
                            
                photo = Photo.get_by_key_name(photo_id)                   
                
                if photo is None:  
                    try:
                        photo = Photo.new_from_xml(photo_xml)
                    except WrongPhoto:
                        continue                                
            
                photo_index = PhotoIndex.get_by_key_name(photo.key().name(), user)
                            
                if photo_index is not None:
                    break   
                else:                
                    photo.favorited_count += 1         
                    
                    if photo.favorited_count == 2:
                        update_skill_date(photo, datetime.datetime.now())
                           
                    photo_index = PhotoIndex(key_name = photo.key().name(),                                         
                                             parent   = user)
                
                    objects_to_put.append(photo)                     
                    objects_to_put.append(photo_index)
                          
            
            logging.info("Updating favorites: %s objects (photos+index)" % len(objects_to_put))
            
            db.put(objects_to_put)                        
            user.put()                                 
            
            if len(objects_to_put) != 0:              
                user.update_subscribers(self.request.get('initial_update'))
                           

class UpdateSubscriberIndexHandler(webapp.RequestHandler):
    def post(self):
        user = User.get(self.request.get('key'))        
        subscriber = User.get(self.request.get('subscriber'))
        
        contact = UserContact.get_by_key_name(user.nsid, subscriber)                        
        
        six_hours_ago = datetime.datetime.now()-datetime.timedelta(minutes=360)
        
        if contact.updated is None or contact.updated < six_hours_ago:                     
            photo_indexes = PhotoIndex.all(keys_only = True)
            photo_indexes.ancestor(user)
            
            if contact.updated is not None and contact.updated:
                photo_indexes.filter("created >", contact.updated)
                            
            photo_indexes.order("-created")            
            photo_indexes = photo_indexes.fetch(flickr.PHOTOS_PER_CONTACT)
            
            objects_to_put = []
                                
            if self.request.get('initial_update'):
                if subscriber.latest_photo:
                    last_photo = UserPhotoIndex.get_by_key_name(subscriber.latest_photo, subscriber)
                    start_from_time = last_photo.created - datetime.timedelta(seconds = 60)
                else:
                    start_from_time = datetime.datetime.now()
            else:
                start_from_time = 0         
                    
                    
            photo_counter = 0
            
            for photo_index_key in photo_indexes:            
                logging.info("photo_index %s", photo_index_key)
                try:
                    user_photo_index = UserPhotoIndex.get_by_key_name(photo_index_key.name(), subscriber)
                except AttributeError:
                    db.delete(db.Key.from_path('UserPhotoIndex', photo_index_key.name(), 'User', subscriber.key().name()))
                    user_photo_index = None
                
                if user_photo_index is None:
                    user_photo_index = UserPhotoIndex(key_name = photo_index_key.name(),
                                                      parent   = subscriber,
                                                      favorited_by = user)
                    
                    if self.request.get('initial_update'):
                        user_photo_index.created = start_from_time - datetime.timedelta(microseconds=(10*photo_counter))
                    else:
                        user_photo_index.created = datetime.datetime.now()                
                        
                    photo_counter += 1
                else:
                    user_photo_index.favorited_count += 1
                                      
                if user_photo_index.favorited_count == 2:
                    update_skill_date(user_photo_index, datetime.datetime.now())
                            
                objects_to_put.append(user_photo_index)
                
                
            logging.info("Updating subscriber index: %s photos" % len(objects_to_put))
            
            db.put(objects_to_put)
            
            contact.updated = datetime.datetime.now()
            contact.put()
            
            try:
                subscriber.latest_photo = objects_to_put[-1].key().name()
                subscriber.put()
            except IndexError:
                pass                
            

class UpdateContactFavoritesHandler(webapp.RequestHandler):
    def get(self):
        user = User.get(self.request.get('key'))
        
        contacts = UserContact.all()
        contacts.filter("user", user.key().name())
        
        if self.request.get('start_from'):
            contacts.filter("__key__ >", db.Key(self.request.get('start_from')))
            
        contacts.order("__key__")
        contacts = contacts.fetch(10)
        
        for user_contact in contacts:
            taskqueue.Task(url="/task/user/update_favorites", 
                           params={"key": db.Key.from_path('User',user_contact.contact)}).add("update-photos")
                           
        if len(contacts) == 10:
            taskqueue.Task(url="/task/user/update_contact_favorites", 
                           params={"key": user.key(), 'start_from':contacts[-1].key()}).add("update-photos")                           
                           
    def post(self):
        self.get()      
                           
                              

class UpdateFavoritesCronHandler(webapp.RequestHandler):
    def get(self, active_status):
        user = User.all().order("last_login")
        user.filter('status', const.UserRegistred)
        
        if self.request.get('start_from'):
            start_from = User.get(self.request.get('start_from'))
                        
            user.filter("last_login >", start_from.last_login)
                
        twenty_four_hours_ago = datetime.datetime.now()-datetime.timedelta(hours=24)
        week_ago = datetime.datetime.now()-datetime.timedelta(weeks=1)
            
        if (active_status == 'active'):
            countdown = 0
            user.filter("last_login >", twenty_four_hours_ago)
        else:
            countdown = 1000
            user.filter("last_login <", twenty_four_hours_ago)
            user.filter("last_login >", week_ago)        
                
        user = user.get() 
        
        if user is not None:                                        
            taskqueue.Task(url="/task/user/update_contact_favorites", 
                           params={"key":user.key()}, countdown=countdown).add("update-photos")
            
            taskqueue.Task(url="/task/update_favorites_cron/%s" % active_status, 
                           params={"start_from":user.key()}, countdown=countdown).add("default")
                
    def post(self, active_status):
        self.get(active_status)                                                 
                
                                                                                                                  
            
class UpdateContactsCronHandler(webapp.RequestHandler):
    def get(self):        
        users = User.all(keys_only = True).order("__key__")
        users.filter('status', const.UserRegistred)        
        
        if self.request.get('start_from'):
            users.filter("__key__ >", db.Key(self.request.get('start_from')))
        
        user_keys = users.fetch(50)
        
        for key in user_keys: 
            taskqueue.Task(url="/task/user/update_contacts", params={"key":key}).add("update-contacts")
            
            
        if len(user_keys) == 50:
            taskqueue.Task(url="/task/update_contacts_cron", params={"start_from":user_keys[-1]}).add("update-contacts")
            
    def post(self):
        self.get()


class UpdateSubscriptionHandler(webapp.RequestHandler):
    def get(self):
        subscriptions = Subscription.all().fetch(100)
        
        for subscription in subscriptions:
            deferred.defer(subscription.update) 


application = webapp.WSGIApplication([
   ('/task/user/update_contacts', UpdateContactsHandler),
   ('/task/update_contacts_cron', UpdateContactsCronHandler),
      
   ('/task/user/update_favorites', UpdateFavesHandler),
   ('/task/user/update_subscriber_index', UpdateSubscriberIndexHandler),
   
   ('/task/user/update_contact_favorites', UpdateContactFavoritesHandler),
   ('/task/update_favorites_cron/([^\/]*)', UpdateFavoritesCronHandler),      
   
   ('/task/update_subscriptions', UpdateSubscriptionHandler)   
   ], debug=True)

            
def main():
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            
