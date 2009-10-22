import logging
import datetime
import time

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api.labs import taskqueue

import flickr
from models import *

class UpdateContactsHandler(webapp.RequestHandler):
    def get(self, user_key):
        CONTACTS_PER_PAGE = 50
            
        user = User.get(user_key)
        
        if user:
            page = self.request.get('page')
            
            try:
                page = int(page)
            except ValueError:
                page = 1
            
            contacts_xml = flickr.call_method("flickr.contacts.getPublicList", 
                                              "user_id=%s&per_page=%s&page=%s" % (user.userid, CONTACTS_PER_PAGE, page))
            
            contacts = []
            
            for contact_xml in contacts_xml.getElementsByTagName('contact'):
                contact_key = db.GqlQuery("SELECT __key__ FROM Contact WHERE __key__ = Key('Contact','c%s')" % contact_xml.getAttribute('nsid')).get()
                
                if contact_key is None:
                    ignored = int(contact_xml.getAttribute('ignored')) == 1
                                    
                    contact = Contact(key_name="c%s" % contact_xml.getAttribute('nsid'),
                                      parent = user,
                                      userid = contact_xml.getAttribute('nsid'),
                                      username = contact_xml.getAttribute('username'),
                                      iconserver = contact_xml.getAttribute('iconserver'),
                                      show_photos = not ignored,
                                      show_favorites = not ignored)
                                    
                    contacts.insert(0, contact)
                
            db.put(contacts)                    
            
            if self.request.get('update_favorites'):
                task = taskqueue.Task(url="/task/update_contacts_faves/%s" % user_key, params={'page': 1}, method = 'GET')
                task.add("non-blocking") # Put first update in not blocking queue
                        
            page = page + 1
            
            if len(contacts) == CONTACTS_PER_PAGE:
                taskqueue.Task(url="/task/update_contacts/%s" % user_key, 
                               params={'page': page}, method = 'GET').add("update-contacts")
        else:
            self.response.out.write("Unknown user")
            logging.error("Can't update contacts. Unknown user %s" % user_key)


class UpdateContactsFavesHandler(webapp.RequestHandler):
    def get(self, user_key):
        PHOTOS_PER_CONTACT = 5
        
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
        
        for item in items:
            photo_key_name = "p%s" % item['image_id']
             
            photo = Photo.get_by_key_name(photo_key_name, user)
            
            favorited_by = str(db.Key.from_path('User', "u%s" % item['favorited_by']))
                    
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
                
                photos.append(photo)                
            else:                
                try:                    
                    photo.favorited_by.index(favorited_by)                                    
                except ValueError:                    
                    photo.favorited_by.append(favorited_by)
                    photo.favorited_count += 1             
                    
                    photos.append(photo)                
            
            
        db.put(photos)
        
        if len(items) != 0:
            page = page + 1
            taskqueue.Task(url="/task/update_contacts_faves/%s" % user_key, 
                           params={'page': page}, method = 'GET').add("update-photos")
        else:
            user.updated_at = datetime.datetime.now()
            
            # We don't want to restart all queue, if user.put gives some errors
            try:
                user.put()
            except:
                user.put()
                

class UpdateFavoritesCronHandler(webapp.RequestHandler):
    def get(self):
        user_keys = db.GqlQuery("SELECT __key__ FROM User WHERE updated_at < :1", datetime.datetime.today()-datetime.timedelta(minutes=29))
        
        for key in user_keys:
            taskqueue.Task(url="/task/update_contacts_faves/%s" % key, method = 'GET').add("update-photos")
            
            
            
class UpdateContactsCronHandler(webapp.RequestHandler):
    def get(self):  
        user_keys = db.GqlQuery("SELECT __key__ FROM User")
        
        for key in user_keys:
            taskqueue.Task(url="/task/update_contacts/%s" % key, method = 'GET').add("update-contacts")                                       
            
            
              
class ClearDatabaseHandler(webapp.RequestHandler):
    def get(self):
        items_for_delete = User.all().fetch(100)
        if len(items_for_delete) == 0:
            items_for_delete = Contact.all().fetch(100)
            if len(items_for_delete) == 0:
                items_for_delete = Photo.all().fetch(100)    
        
        if len(items_for_delete) != 0:
            db.delete(items_for_delete)            
            taskqueue.Task(url="/task/clear_database", method = 'GET').add("non-blocking")


application = webapp.WSGIApplication([
   ('/task/update_contacts/([^\/]*)', UpdateContactsHandler),
   ('/task/update_contacts_faves/([^\/]*)', UpdateContactsFavesHandler),
   ('/task/clear_database', ClearDatabaseHandler),
   ('/task/update_favorites_cron', UpdateFavoritesCronHandler)
   ('/task/update_contacts_cron', UpdateFavoritesCronHandler)
   ], debug=True)
                
def main():
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            