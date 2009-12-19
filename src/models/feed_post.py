'''
Created on 04.12.2009

@author: buger
'''
               
class FeedPost(db.Model):        
    content = db.TextProperty()
    created_at = db.DateTimeProperty(auto_now = True)    