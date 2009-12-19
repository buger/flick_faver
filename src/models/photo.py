'''
Created on 04.12.2009

@author: buger
'''

from google.appengine.ext import db
from models.user import User        

import const
import flickr

class WrongPhoto(Exception):
    pass

def update_skill_date(photo, date):
    photo.skill_changed_date = date
    
    year, week, weekday = date.isocalendar()
    
    photo.skill_changed_year  = year
    photo.skill_changed_month = date.month        
    photo.skill_changed_week  = week        
    photo.skill_changed_day   = date.day

class Photo(db.Expando):        
    title    = db.StringProperty(indexed = False) 
    
    image_url   = db.LinkProperty(indexed = False)
    
    favorited_count = db.IntegerProperty(default = 0)
    
    author     = db.StringProperty(indexed = False)
    author_uri = db.LinkProperty(indexed = False)
        
    created   = db.DateTimeProperty(auto_now_add = True)
    
    @property
    def photo_id(self):
        return self.key().name()
    
    @property
    def uri(self):
        return "%s/%s" % (self.author_uri, self.photo_id)
    
    @property
    def image_m_url(self):
        return self.image_url.replace('.jpg','_m.jpg')
    
    @property
    def image_s_url(self):
        return self.image_url.replace('.jpg','_s.jpg')    
    
    def update_created_index(self):
        year, week, weekday = self.created.isocalendar()
        day = self.created.day
        month = self.created.month
        
        self.year  = year
        self.month = month        
        self.week  = week
        self.day   = day 
        
        
    @classmethod
    def new_from_xml(cls, photo_xml):
        photo_id  = photo_xml.getAttribute('id')
        user_path = photo_xml.getAttribute('pathalias')
        url_m     = photo_xml.getAttribute('url_m')
        author    = photo_xml.getAttribute('ownername')
        title     = photo_xml.getAttribute('title')
        
        if len(user_path) == 0:
            user_path = photo_xml.getAttribute("owner")
                                                                
        if len(url_m) == 0:
            raise WrongPhoto
        
        photo = Photo(key_name = photo_id,                            
                      uri      = flickr.photo_uri(user_path, photo_id),
                      title    = title,                                  
                      image_url   = url_m,                                  
                      author     = author,
                      author_uri = flickr.user_uri(user_path)                                                        
                      )                        
        
        return photo
    

# Parent of PhotoIndex is User object
class PhotoIndex(db.Expando):
    created = db.DateTimeProperty(auto_now_add = True)
    
class UserPhotoIndex(PhotoIndex):            
    favorited_count = db.IntegerProperty(default = 1)
    favorited_by    = db.StringProperty()    