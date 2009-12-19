'''
Created on 04.12.2009

@author: buger
'''
   
class RSSFeed(db.Model):
    last_photo = db.StringProperty()
    content = db.TextProperty()
    updated_at = db.DateTimeProperty(auto_now = True)
    
    @property
    def etag(self):
        return hashlib.sha1(db.model_to_protobuf(self).Encode()).hexdigest()
