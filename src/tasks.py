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
        user_key = self.request.get('user_key')
        
        if self.request.get('photos-per-contact'):
            PHOTOS_PER_CONTACT = int(self.request.get('photos-per-contact'))
        else:
            PHOTOS_PER_CONTACT = 10
        
        user = User.get(user_key)
                
        page = self.request.get('page')
        
        try:
            page = int(page)
        except ValueError:
            page = 1
                        
        photos = []
        
        items = flickr.get_contacts_faves(user_key = user_key,
                                          truncate = PHOTOS_PER_CONTACT,
                                          page = page)
        
        
        if self.request.get('travel-in-time'):
            last_photo = db.GqlQuery("SELECT * FROM Photo WHERE ANCESTOR IS :1 ORDER BY created_at", user).get()
            
            if last_photo:
                start_from_time = last_photo.created_at - datetime.timedelta(seconds = 60)
            else:
                start_from_time = datetime.datetime.now()
        else:
            start_from_time = 0
                        
        # in groups of PHOTOS_PER_CONTACT, each group will have photos from one contact 
        contact_groups = itertools.izip(*[itertools.islice(items, i, None, PHOTOS_PER_CONTACT) for i in range(PHOTOS_PER_CONTACT)])
        
        counter = 1
        
        for group in contact_groups:
            favorited_by = str(db.Key.from_path("User","u%s" % user.userid, "Contact","c%s" % group[0]['favorited_by']))
                                    
            for item in group:
                photo_key_name = "p%s" % item['image_id']
                
                try:
                    photo = Photo.get_by_key_name(photo_key_name, user)
                except:
                    continue
                
                        
                if photo is None:            
                    published_date = datetime.datetime(*time.strptime(item['published'], "%Y-%m-%dT%H:%M:%SZ")[:6])                                                                
                    
                    photo = Photo(key_name = photo_key_name,
                                  parent   = user,
                                  photo_id = int(item['image_id']),                              
                                  uri      = item['link'],
                                  title    = item['title'],
                                  
                                  phtoto_type = const.PhotoTypeFavorite,
                                  
                                  image_url   = item['image_url'],
                                  image_s_url = item['image_s_url'],
                                  image_m_url = item['image_m_url'],
                                  
                                  favorited_by    = [favorited_by],                              
                                  favorited_count = 1,
                                  
                                  author     = item['author']['name'],
                                  author_uri = item['author']['uri'],
                                  
                                  published = published_date                                                        
                                  )
                    
                    if self.request.get('travel-in-time'):
                        photo.created_at = start_from_time - datetime.timedelta(microseconds=(10*counter))
                    else:
                        photo.created_at = datetime.datetime.now()
                    
                    photos.append(photo) 
                    
                    counter += 1               
                else:                
                    try:                    
                        photo.favorited_by.index(favorited_by)
                        
                        logging.debug("breaking!:)")
                        break #go back to parent cycle, all next photos already in database                                    
                    except ValueError:                    
                        photo.favorited_by.append(favorited_by)
                        photo.favorited_count += 1             
                        
                        photos.append(photo)   
            
        logging.debug("New photos: %s" % len(photos))
        
        db.put(photos)
        
        if len(items) != 0:
            page = page + 1
            task = taskqueue.Task(url="/task/update_contacts_faves", 
                                  params={'user_key': user_key,
                                          'page': page, 
                                          'non-blocking':self.request.get('non-blocking'), 
                                          'travel-in-time': self.request.get('travel-in-time'),
                                          'photos-per-contact': self.request.get('photos-per-contact')}, 
                                  method = 'GET')
            
            if self.request.get('non-blocking'):
                task.add("non-blocking")
            else:
                task.add("update-photos")
        else:
            user.updated_at = datetime.datetime.now()
            user.processing_state = const.StateWaiting
            # We don't want to restart all queue, if user.put gives some errors
            try:
                user.put()
            except:
                user.put()
                

class UpdateFavoritesCronHandler(webapp.RequestHandler):
    def get(self):
        users = db.GqlQuery("SELECT * FROM User WHERE updated_at < :1 AND processing_state = :2", 
                            datetime.datetime.now()-datetime.timedelta(minutes=60), const.StateWaiting) 
        
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
            
            
              
class ClearDatabaseHandler(webapp.RequestHandler):
    def get(self):
        #items_for_delete = User.all().fetch(100)
        #if len(items_for_delete) == 0:
        #    items_for_delete = Contact.all().fetch(100)
        #    if len(items_for_delete) == 0:
        items_for_delete = Photo.all().fetch(100)    
        
        if len(items_for_delete) != 0:
            db.delete(items_for_delete)            
            taskqueue.Task(url="/task/clear_database", method = 'GET').add("non-blocking")


class UserUpdateProcessingStateHandler(webapp.RequestHandler):
    def get(self):
        users = User.all().fetch(300)
        
        for user in users:
            user.processing_state = const.StateWaiting
        
        db.put(users)

application = webapp.WSGIApplication([
   ('/task/update_contacts', UpdateContactsHandler),
   ('/task/update_contacts_faves', UpdateContactsFavesHandler),
   ('/task/clear_database', ClearDatabaseHandler),
   ('/task/update_favorites_cron', UpdateFavoritesCronHandler),
   ('/task/update_contacts_cron', UpdateContactsCronHandler),
   
   ('/task/update_processing_state', UserUpdateProcessingStateHandler)   
   ], debug=True)
                
def main():
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            
