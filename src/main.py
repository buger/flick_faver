import datetime
import logging
import os
import itertools

import const

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db

from google.appengine.api.urlfetch import DownloadError

from appengine_utilities.sessions import Session

from models import *
from config import *
import flickr
 
 
PHOTOS_PER_LOAD = 30
         
def doRender(handler, tname='index.html', values={}, options = {}):
    temp = os.path.join(
        os.path.dirname(__file__),
        'templates/' + tname)
    if not os.path.isfile(temp):
        return False
    
    # Make a copy of the dictionary and add the path
    newval = dict(values)
    newval['path'] = handler.request.path
    
    handler.session = Session()
    
    try:
        newval['username'] = handler.session['username']
        newval['fullname'] = handler.session['username']
        newval['auth_token'] = handler.session['auth_token']        
    except KeyError:
        pass
    
    
    newval['is_admin'] = users.is_current_user_admin()
     
#    handler.session = Session()
#        newval['username'] = handler.session['username']
#    if 'username' in handler.session:
                    
    outstr = template.render(temp, newval)
                
    if 'render_to_string' in options:
        return outstr
    else:
        handler.response.out.write(outstr)
        return True 
 
def get_photos(page, start_from = None):
    session = Session()
    
    current_user = db.Key.from_path('User',"u%s" % session['userid'])
        
    offset = (page-1)*PHOTOS_PER_LOAD
    
    if start_from:                
        start_from_photo = Photo.get(start_from)
        
        photos = Photo.gql("WHERE created_at < :1 AND ANCESTOR IS :2 ORDER BY created_at DESC", start_from_photo.created_at, current_user).fetch(PHOTOS_PER_LOAD, offset)
    else:
        photos = Photo.gql("WHERE ANCESTOR IS :1 ORDER BY created_at DESC", current_user).fetch(PHOTOS_PER_LOAD, offset)
                        
    # in groups of 3
    photos_groups = itertools.izip(*[itertools.islice(photos, i, None, 3) for i in range(3)])
    
    return photos_groups
        
 
class MainHandler(webapp.RequestHandler):
    def get(self):
        doRender(self, "index.html")
        
class LoadPhotosHandler(webapp.RequestHandler):
    def post(self, page):        
        page = int(page)
        photo_key = self.request.get("photo_key")
        
        session = Session()
        
        try:
            userid = session['userid']
            photos_groups = get_photos(page = page, start_from = photo_key)
        except KeyError:                    
            photos_groups = []     
        
        doRender(self, "_photos.html", {'photos_groups':photos_groups})
              

class LoginHandler(webapp.RequestHandler):
    def get(self):               
        if self.request.get('userid'):
            self.redirect("/auth_callback?userid=%s" % self.request.get('userid'))
        else:
            self.redirect(flickr.FLICKR_AUTH_URL)
        
class AuthCallbackHandler(webapp.RequestHandler):
    def get(self):
        try:
            if self.request.get('userid'):
                user_info = flickr.FlickrUserInfo("", self.request.get('userid'), self.request.get('userid'), "")
            else:
                frob = self.request.get('frob')                        
                
                try:
                    user_info = flickr.get_user_info(frob)
                except:
                    user_info = flickr.get_user_info(frob)                
            
        
            user = User.get_by_key_name("u%s" % user_info.userid)
            
            session = Session()
                    
            if not user:
                user = User(key_name = "u%s" % user_info.userid,
                            userid   = user_info.userid,
                            username = user_info.username,
                            fullname = user_info.fullname,
                            updated_at = datetime.datetime.now(),
                            last_login = datetime.datetime.now())
                user.put()
                
                taskqueue.Task(url="/task/update_contacts/%s" % user.key(), 
                               params={'update_favorites':True}, method = 'GET').add("update-contacts")                           
            else:
                user.last_login = datetime.datetime.now()
                
                try:
                    user.put()
                except:
                    user.put()
                    
            session["username"]   = user.username
            session["fullname"]   = user.fullname
            session["userid"]     = user.userid
            session["auth_token"] = user_info.auth_token        
        except ValueError:
            pass
                                                                        
        self.redirect("/")
        
class LogoutHandler(webapp.RequestHandler):
    def get(self):
        session = Session()
        session.delete()
        
        self.redirect("/")        
        
 
application = webapp.WSGIApplication([
   ('/', MainHandler),
   ('/photos/([^\/]*)', LoadPhotosHandler),
   ('/login', LoginHandler),
   ('/logout', LogoutHandler),
   ('/auth_callback', AuthCallbackHandler)
   ], debug=True)
                
def main():
    if os.environ.get('SERVER_SOFTWARE') == 'Development/1.0':
        os.environ['USER_IS_ADMIN'] = '1'
    
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            