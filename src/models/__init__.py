import const
import hashlib
from google.appengine.ext import db

# For templates, using in tag clouds
class PhotoTeplateObject:
    def __init__(self, photo_id, image_url, title, author, author_url, published):
        self.photo_id = photo_id
        self.image_url = image_url
        self.title = title
        self.author = author
        self.author_url = author_url
        self.published = published
     
        
class User(db.Model):
    username  = db.StringProperty(required = True)
    userid    = db.StringProperty(required = True)
    fullname  = db.StringProperty()
    
    last_login = db.DateTimeProperty()
    updated_at = db.DateTimeProperty() # Last favorites update 
    created_at = db.DateTimeProperty(auto_now_add = True)
    
    processing_state = db.IntegerProperty(choices=set([const.StateProcessing, const.StateWaiting]))      
          

class Photo(db.Expando):        
    photo_id = db.IntegerProperty(required = True)
    uri      = db.LinkProperty()
    title    = db.StringProperty() 
    
    image_url   = db.LinkProperty()
    image_m_url = db.LinkProperty() # Medium
    image_s_url = db.LinkProperty() # Square
    
    favorited_count = db.IntegerProperty(default = 0)
    favorited_by    = db.StringListProperty(default = [])
    
    author     = db.StringProperty()
    author_uri = db.LinkProperty()
    
    skill_level  = db.IntegerProperty(default = 0) # Favorited more the 1 contact    
    
    #published_at = db.DateTimeProperty()
    created_at   = db.DateTimeProperty()
    updated_at   = db.DateTimeProperty(auto_now = True)       

class Contact(db.Model):
    username       = db.StringProperty(required = True)
    userid         = db.StringProperty(required = True)    
    
    iconserver     = db.StringProperty()
    
    type           = db.IntegerProperty(choices=set([const.ContactSimple,const.ContactFriend,const.ContactFamily]))
    show_photos    = db.BooleanProperty(default = True)
    show_favorites = db.BooleanProperty(default = True)    
    state          = db.IntegerProperty(choices=set([const.UserStateRegistred, const.UserStateUnRegistred]))
    
    created_at  = db.DateTimeProperty(auto_now_add = True)
    
class RSSFeed(db.Model):
    last_photo = db.StringProperty()
    content = db.TextProperty()
    updated_at = db.DateTimeProperty(auto_now = True)
    
    @property
    def etag(self):
        return hashlib.sha1(db.model_to_protobuf(self).Encode()).hexdigest()
    
class FeedPost(db.Model):        
    content = db.TextProperty()
    created_at = db.DateTimeProperty(auto_now = True)    