import datetime
import logging
import os
import itertools
import urllib

import const

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.api import memcache
from google.appengine.ext.webapp import template
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.api.labs import taskqueue
from google.appengine.ext import db

from google.appengine.api.urlfetch import DownloadError

from appengine_utilities.sessions import Session

from models.user import User
from models.photo import *
from models.subscription import *

from config import *
import utils
import flickr
 
template.register_template_library('template_filters.date')

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
        newval['nsid'] = handler.session['nsid']
        newval['fullname'] = handler.session['username']
        newval['auth_token'] = handler.session['auth_token']
                
        if 'difficulty' not in handler.session:
            newval["difficulty"] = 0
                        
        if 'layout' not in handler.session:
            newval["layout"] = const.LayoutMedium
            
        newval['difficulty'] = handler.session['difficulty']        
        newval['layout'] = handler.session['layout']                                      
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
 
def get_photos(page, start_from = None, difficulty = 0, layout = None):
    session = Session()
                        
    if layout == const.LayoutBig:
        photos_in_group = 1
        photos_per_load = 10
    elif layout == const.LayoutMedium:
        photos_in_group = 3
        photos_per_load = 21
    else:
        photos_in_group = 6
        photos_per_load = 60    
    
    current_user = db.Key.from_path('User',session['nsid'])
    
    if page == 1:
        user = User.get(current_user)
        
        user.layout = layout
        session['layout'] = user.layout
        
        user.difficulty = int(difficulty)
        session['difficulty'] = user.difficulty
        
        user.put()
    
        
    offset = (page-1)*photos_per_load
    
    start_from_photo = None
    
    photo_keys = UserPhotoIndex.all(keys_only = True)    
    photo_keys.ancestor(current_user)
    
    if difficulty == const.SkillLevelEasy:
        photo_keys.order('-skill_changed_date')
    else:
        photo_keys.order('-created')
    
    if start_from:                        
        start_from_photo = UserPhotoIndex.get_by_key_name(start_from, current_user)
        
        if difficulty == const.SkillLevelEasy:
            photo_keys.filter('skill_changed_date < ', start_from_photo.skill_changed_date)
        else:
            photo_keys.filter('created < ', start_from_photo.created)
        
        photo_keys = photo_keys.fetch(photos_per_load)
    else:
        photo_keys = photo_keys.fetch(photos_per_load, offset)

    photos = [Photo.get_by_key_name(photo_key.name()) for photo_key in photo_keys]
    
    # in groups of 3
    photos_groups = [itertools.islice(photos, i*photos_in_group, (i+1)*photos_in_group, 1) for i in range(photos_per_load/photos_in_group)]          
    
    if len(photos) == 0:
        last_date = None
    else:
        last_photo = UserPhotoIndex.get(photo_keys[0])
        
        if difficulty == const.SkillLevelEasy:
            last_date = last_photo.skill_changed_date
        else:
            last_date = last_photo.created
        
    return (photos_groups, start_from_photo, last_date)
        
        
class OriginalImageHandler(webapp.RequestHandler):
    def post(self, photo_id):
        session = Session()
        
        self.response.out.write(flickr.original_image_url(photo_id, session['auth_token']))
        
class FavoriteStatusHandler(webapp.RequestHandler):
    def post(self, photo_id):
        session = Session()
         
        photo = UserPhotoIndex.get_by_key_name(photo_id, db.Key.from_path('User', session['nsid']))
                
        self.response.out.write(photo.favorite)        
 
 
class FavoriteImageHandler(webapp.RequestHandler):
    def post(self, action, photo_id):
        session = Session()
         
        photo = UserPhotoIndex.get_by_key_name(photo_id, db.Key.from_path('User', session['nsid']))
         
        if action == "add":
            result = flickr.favorite(photo_id, session["auth_token"])
             
            if result == "success":
                photo.favorite = 1
                db.put(photo)
             
            self.response.out.write(result)
             
        elif action == "remove":
            result = flickr.remove_favorite(photo_id, session["auth_token"])
            
            if result == "success":
                photo.favorite = 0
                db.put(photo) 
                      
            self.response.out.write(result)
            
class MainHandler(webapp.RequestHandler):
    def get(self):
        photos = Photo.all().order("-skill_changed_date")
        
        try:
            photos = photos.fetch(10)
        except:
            try:
                photos = photos.fetch(10)
            except:
                photos = []
                                
        doRender(self, "index.html", {'photos':photos})

class UserHandler(webapp.RequestHandler):
    def get(self):
        session = Session()
                
        if 'username' not in session:
            self.redirect("/")         
        
        doRender(self, "dashboard.html")
        
class LoadPhotosHandler(webapp.RequestHandler):
    def post(self, page):
        page_type = self.request.get('page_type')                                
        page = int(page)
        photo_key = self.request.get("last_photo_id")
                
        
        if page_type == 'simple':
            difficulty = int(self.request.get('difficulty'))                                
            layout = int(self.request.get('layout'))
            
            #try:
            photos_groups, last_photo, first_date = get_photos(page = page, start_from = photo_key, difficulty = difficulty, layout = layout)
            #except KeyError:                    
            #    photos_groups = []
            #    last_photo = None
            #    first_date = None            
            
            doRender(self, "_photos.html", {'photos_groups':photos_groups, 'first_date':first_date, 'layout':layout})
        elif page_type == 'main_big':
            photos = Photo.all().order("-skill_changed_date")
            photos = photos.fetch(10, 10*(page-1))            
            
            doRender(self, "_photos_big.html", {'photos': photos})
        else:
            self.error(404)   

class LoginHandler(webapp.RequestHandler):
    def get(self):               
        if self.request.get('userid'):
            self.redirect("/auth_callback?userid=%s" % self.request.get('userid'))
        else:
            self.redirect(flickr.FLICKR_AUTH_URL)
        
class AuthCallbackHandler(webapp.RequestHandler):
    def get(self):
        if self.request.get('userid'):
            user_info = flickr.FlickrUserInfo("", self.request.get('userid'), self.request.get('userid'), "")
        else:
            frob = self.request.get('frob')                        
            
            try:
                user_info = flickr.get_user_info(frob)
            except:
                user_info = flickr.get_user_info(frob)                
        
    
        user = User.get_by_key_name(user_info.nsid)
        
        session = Session()

        if user is None:
            user = User(key_name = user_info.nsid,
                        username = user_info.username,
                        fullname = user_info.fullname, 
                        token    = user_info.token,     
                        status   = const.UserRegistred,                      
                        last_login = datetime.datetime.now())
                     
        task = None
        
        if not user.is_saved() or user.status == const.UserUnRegistred:
            task = taskqueue.Task(url="/task/user/update_contacts", 
                                  params={'key':user.key(), 'update_favorites':True, 'initial_update': True})                           
        
        user.status = const.UserRegistred
        user.username = user_info.username
        user.fullname = user.fullname
        user.token = user_info.token
        
        if os.environ.get('SERVER_SOFTWARE') == 'Development/1.0':
            user.token = '72157623100491721-4ab7039d8e6b4615' 
        #user.token = '72157622500427269-7131c791b2204f16'
        user.last_login = datetime.datetime.now()
        
        try:
            user.put()
        except:
            user.put()
        
        if task:
            task.add("non-blocking")
        
        session["username"]   = user.username
        
        if user.fullname:
            session["fullname"]   = user.fullname
            
        session["nsid"]     = user.nsid
        session["auth_token"] = user.token
        
        session["difficulty"] = user.difficulty
        session["layout"] = user.layout        
                                                                        
        self.redirect("/dashboard")
        
class LogoutHandler(webapp.RequestHandler):
    def get(self):
        session = Session()
        session.delete()
        
        self.redirect("/")        
        
 
class RSSHandler(webapp.RequestHandler):                 
    def get(self, userid):
        HTTP_DATE_FMT = "%a, %d %b %Y %H:%M:%S GMT"
        
        userid = urllib.unquote_plus(urllib.unquote(userid))
        
        user = User.get_by_key_name(userid)
        
        if user is None:
            self.error(404)
        else:                           
            subscription = Subscription.get_by_key_name(userid, user)
            
            if subscription is None:
                subscription = Subscription(parent = user, 
                                            key_name = userid, 
                                            subscription_type = 0)
                subscription.put()
                
                content = template.render("templates/_rss_welcome_post.html", {'user': user})
                welcome_post = Post(parent = subscription, content = content)
                welcome_post.put()
                
            self.response.headers['Content-Type'] = 'application/atom+xml; charset=utf-8'
                    
            if subscription.updated_at:
                last_modified = subscription.updated_at.strftime(HTTP_DATE_FMT)            
                self.response.headers['Last-Modified'] = last_modified
                
            self.response.headers['ETag'] = '"%s"' % subscription.etag
                            
    
            posts = Post.all().ancestor(subscription).order("-updated_at").fetch(5)
        
            feed_content = template.render("templates/atom.xml", {'user':user, 'posts':posts})
                
            self.response.out.write(feed_content)            
            
 
application = webapp.WSGIApplication([
   ('/', MainHandler),
   ('/dashboard', UserHandler),
   ('/photos/([^\/]*)', LoadPhotosHandler),
   ('/original_image/([^\/]*)', OriginalImageHandler),
   ('/favorite_status/([^\/]*)', FavoriteStatusHandler),
   ('/favorites/([^\/]*)/([^\/]*)', FavoriteImageHandler),
   ('/login', LoginHandler),
   ('/logout', LogoutHandler),
   ('/auth_callback', AuthCallbackHandler),
   ('/(?:feed|user)/([^\/]*)', RSSHandler)   
   ], debug=True)
                
def main():
    if os.environ.get('SERVER_SOFTWARE') == 'Development/1.0':
        os.environ['USER_IS_ADMIN'] = '1'
    
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            
