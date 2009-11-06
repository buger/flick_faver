import logging
import datetime
import time
import itertools

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db

import flickr
from models import *

class UpdateContactsHandler(webapp.RequestHandler):
    def get(self):
        CONTACTS_PER_PAGE = 50
        
        user_key = self.request.get('user_key')
        
        user = User.get(user_key)
        
        if user:
            page = self.request.get('page')
            
            try:
                page = int(page)
            except ValueError:
                page = 1
            
            logging.info("params: %s" % "user_id=%s&per_page=%s&page=%s" % (user.userid, CONTACTS_PER_PAGE, page))
            response = flickr.call_method("flickr.contacts.getPublicList", 
                                          "user_id=%s&per_page=%s&page=%s" % (user.userid, CONTACTS_PER_PAGE, page))
            
            contacts = []
            
            contacts_root_xml = response.getElementsByTagName('contacts')[0]
            max_pages = int(contacts_root_xml.getAttribute('pages'))

            contacts_xml = response.getElementsByTagName('contact')
            logging.info("Contacts size xml: %s" % len(contacts_xml))

            for contact_xml in contacts_xml:
                contact_key = db.Key.from_path("User","u%s" % user.userid, "Contact","c%s" % contact_xml.getAttribute('nsid'))

                contact = Contact.get(contact_key)
                
                if contact is None:
                    ignored = int(contact_xml.getAttribute('ignored')) == 1
                                    
                    contact = Contact(key_name="c%s" % contact_xml.getAttribute('nsid'),
                                      parent = user,
                                      userid = contact_xml.getAttribute('nsid'),
                                      username = contact_xml.getAttribute('username'),
                                      iconserver = contact_xml.getAttribute('iconserver'),
                                      show_photos = not ignored,
                                      show_favorites = not ignored)
                                    
                    contacts.insert(0, contact)
                
            logging.info("Contacts size for put: %s" % len(contacts))
            db.put(contacts)                    
            
            if self.request.get('update_favorites'):
                task = taskqueue.Task(url="/task/update_contacts_faves", 
                                      params={'user_key':user_key, 'page': 1, 'travel-in-time': 1, 'non-blocking': 1,'photos-per-contact':10}, method = 'GET')
                task.add("non-blocking") # Put first update in not blocking queue
                                        
            if page <= max_pages:
                page = page + 1

                taskqueue.Task(url="/task/update_contacts", 
                               params={'user_key':user_key, 'page': page}, method = 'GET').add("update-contacts")
        else:
            self.response.out.write("Unknown user")
            logging.error("Can't update contacts. Unknown user %s" % user_key)


class UpdateContactsFavesHandler(webapp.RequestHandler):
    def get(self):
        if self.request.get('photos-per-contact'):
            PHOTOS_PER_CONTACT = int(self.request.get('photos-per-contact'))
        else:
            PHOTOS_PER_CONTACT = 20

        user_key = self.request.get('user_key')            
        user = User.get(user_key)        
                
        # Getting contacts
        contacts = Contact.all()
        contacts.order('__key__')
        contacts.ancestor(user) 

        if self.request.get('last_contact_key'):
            contacts.filter('__key__ >', db.Key(self.request.get('last_contact_key')))

        contacts = contacts.fetch(3)

        
        if self.request.get('travel-in-time'):
            last_photo = db.GqlQuery("SELECT * FROM Photo WHERE ANCESTOR IS :1 ORDER BY created_at", user).get()
            
            if last_photo:
                start_from_time = last_photo.created_at - datetime.timedelta(seconds = 60)
            else:
                start_from_time = datetime.datetime.now()
        else:
            start_from_time = 0                        

        photos = []
        counter = 0
            
        for contact in contacts:
            photos_xml = flickr.get_contact_faves(contact.userid, PHOTOS_PER_CONTACT)
                                    
            for p_xml in photos_xml:
                photo_key_name = "p%s" % p_xml.getAttribute('id')
                
                try:
                    photo = Photo.get_by_key_name(photo_key_name, user)
                except:
                    continue
                                        
                if photo is None:            
                    user_path = p_xml.getAttribute('pathalias')
                    if len(user_path) == 0:
                        user_path = p_xml.getAttribute("owner")
                    
                    
                    logging.debug("url_m:"+p_xml.getAttribute('url_m'))
                    logging.debug("url_sq:"+p_xml.getAttribute('url_sq'))
                    logging.debug("url_s:"+p_xml.getAttribute('url_s'))
                    
                    url_m = p_xml.getAttribute('url_m')
                    if len(url_m) == 0:
                        url_m = p_xml.getAttribute('url_s') 
                    
                    photo = Photo(key_name = photo_key_name,
                                  parent   = user,
                                  photo_id = int(p_xml.getAttribute('id')),                              
                                  uri      = ("http://www.flickr.com/photos/%s/%s" % (user_path, p_xml.getAttribute('id'))),
                                  title    = p_xml.getAttribute('title'),
                                  
                                  phtoto_type = const.PhotoTypeFavorite,
                                  
                                  image_url   = url_m,
                                  image_s_url = p_xml.getAttribute('url_sq'),
                                  image_m_url = p_xml.getAttribute('url_s'),
                                  
                                  favorited_by    = [str(contact.key())],                              
                                  favorited_count = 1,
                                  
                                  author     = p_xml.getAttribute('ownername'),
                                  author_uri = ("http://www.flickr.com/photos/%s" % user_path)                                                        
                                  )
                    
                    if self.request.get('travel-in-time'):
                        photo.created_at = start_from_time - datetime.timedelta(microseconds=(10*counter))
                    else:
                        photo.created_at = datetime.datetime.now()
                    
                    photos.append(photo) 
                    
                    counter += 1               
                else:                
                    try:                    
                        photo.favorited_by.index(str(contact.key()))
                        
                        logging.debug("breaking!:)")
                        break #go back to parent cycle, all next photos already in database                                    
                    except ValueError:                    
                        photo.favorited_by.append(str(contact.key()))
                        photo.favorited_count += 1  
                        
                        if photo.favorited_count == 2:
                            photo.skill_level = 1                                                                                                                   
                            photos.append(photo)   
                    
        logging.debug("New photos: %s" % len(photos))
                
        db.put(photos)
                
        if len(contacts) < 3:        
            user.updated_at = datetime.datetime.now()
            user.processing_state = const.StateWaiting
            # We don't want to restart all queue, if user.put gives some errors
            try:
                user.put()
            except:
                user.put()
                            
        else:
            if self.request.get('non-blocking'):
                countdown = 0
            else:
                countdown = 60
    
            task = taskqueue.Task(url="/task/update_contacts_faves", 
                                  countdown = countdown,
                                  params={'user_key': user_key,
                                          'last_contact_key': contacts[-1].key(), 
                                          'non-blocking':self.request.get('non-blocking'), 
                                          'travel-in-time': self.request.get('travel-in-time'),
                                          'photos-per-contact': self.request.get('photos-per-contact')}, 
                                  method = 'GET')
                
            if self.request.get('non-blocking'):
                task.add("non-blocking")
            else:
                task.add("update-photos")
                

class UpdateFavoritesCronHandler(webapp.RequestHandler):
    def get(self):
        users = db.GqlQuery("SELECT * FROM User WHERE updated_at < :1 AND processing_state = :2", 
                            datetime.datetime.now()-datetime.timedelta(minutes=180), const.StateWaiting) 
        
        for user in users:            
            # If user is active in 24 hours, update every hour, else one at day
            yesterday = datetime.datetime.now()-datetime.timedelta(hours=24)
            
            if user.last_login > yesterday or (user.last_login < yesterday and user.updated_at < yesterday):
                taskqueue.Task(url="/task/update_contacts_faves", params={"user_key":user.key()},method = 'GET').add("update-photos")                                            
                
                user.processing_state = const.StateProcessing
                user.put()                                 
            
class UpdateContactsCronHandler(webapp.RequestHandler):
    def get(self):        
        user_keys = db.GqlQuery("SELECT __key__ FROM User")
        
        for key in user_keys:
            taskqueue.Task(url="/task/update_contacts", params={"user_key":key}, method = 'GET').add("update-contacts")                                                   


class UserUpdateProcessingStateHandler(webapp.RequestHandler):
    def get(self):
        users = User.all().fetch(300)
        
        for user in users:
            user.processing_state = const.StateWaiting
        
        db.put(users)
        
class UpdateSkillLevelHandler(webapp.RequestHandler):
    def get(self):
        photo_key = self.request.get('key')
        
        if photo_key:
            photo = Photo.gql("WHERE __key__ > :1 ORDER BY __key__", db.Key(photo_key)).get()
        else:
            photo = Photo.gql("ORDER BY __key__").get()
                
        try:
            del photo.skill_levels
        except:
            pass
        
        try:    
            del photo.published_at
        except:
            pass
        
        try:            
            del photo.photo_type
        except:
            pass
        
        if photo.favorited_count > 1:                            
            photo.skill_level = 1            
        else:
            photo.skill_level = 0
        
        photo.put()
        
        taskqueue.Task(url="/task/update_skill_level", params={"key":photo.key()}, method = 'GET').add("non-blocking")
    

application = webapp.WSGIApplication([
   ('/task/update_contacts', UpdateContactsHandler),
   ('/task/update_contacts_faves', UpdateContactsFavesHandler),
   ('/task/update_favorites_cron', UpdateFavoritesCronHandler),
   ('/task/update_contacts_cron', UpdateContactsCronHandler),
   ('/task/update_skill_level', UpdateSkillLevelHandler),
   ('/task/update_processing_state', UserUpdateProcessingStateHandler)   
   ], debug=True)
                
def main():
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            
