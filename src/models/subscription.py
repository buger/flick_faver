from google.appengine.ext.webapp import template

from models.photo import *
from models.user import User

import hashlib
import itertools
import datetime

# Parent is Subscription
class Post(db.Model):        
    content = db.TextProperty()
    updated_at = db.DateTimeProperty()    
       
# Parent is User
class Subscription(db.Model):
    subscription_type = db.IntegerProperty()
    updated_at        = db.DateTimeProperty()
    
    @property
    def etag(self):
        return hashlib.sha1(db.model_to_protobuf(self).Encode()).hexdigest()

    def update(self):
        posts_len = Post.all(keys_only = True).ancestor(self).count()
                                        
        photo_keys = UserPhotoIndex.all(keys_only = True)        
        photo_keys.ancestor(self.parent())
        photo_keys.order("created")
        
        if self.updated_at:        
            photo_keys.filter("created >", self.updated_at)
                            
        photo_keys = photo_keys.fetch(60)
        
        def _tnx(item):
            db.put(item)                      
        
        if len(photo_keys) < 10:
            return False          
            
        photos = [Photo.get_by_key_name(photo_key.name()) for photo_key in photo_keys]                        
        
        groups_of_30 = [itertools.islice(photos, i*30, (i+1)*30, 1) for i in range(3)]                
        
        for group in groups_of_30:
            group = list(group)
            
            if len(group) != 0:
                groups_of_3 = [itertools.islice(group, i*3, (i+1)*3, 1) for i in range(10)]                    
                
                content = template.render("templates/_rss_post.html", {'groups_of_3':groups_of_3})
                content = unicode(content, 'utf-8', errors='ignore')
                
                post = None
                
                if posts_len < 5:       
                    post = Post(parent = self, content=content, updated_at = datetime.datetime.now())      
                    posts_len += 1
                else:
                    post = Post.all().ancestor(self).order("updated_at").get()
                    post.updated_at = datetime.datetime.now()
                    post.content = content
                
                                                
                db.run_in_transaction(_tnx, post)   
        
        photo = UserPhotoIndex.get(photo_keys[-1])                        
        self.updated_at = photo.created
        db.run_in_transaction(_tnx, self)
        
                
                
                                                                       