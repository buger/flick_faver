import cgi
import os
import re
import time
import datetime
import random
import logging
import string
import urllib

from google.appengine.ext import webapp

from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.api.labs import taskqueue

from google.appengine.api import urlfetch
from xml.dom import minidom 

 
from config import *

from appengine_utilities.sessions import Session

FLICKR_API_KEY = 'e5504def2a46e4a654ace751ab1cca88'


# For templates, using in tag clouds
class Photo:
    def __init__(self, photo_id, image_url, title, author, author_url, published):
        self.photo_id = photo_id
        self.image_url = image_url
        self.title = title
        self.author = author
        self.author_url = author_url
        self.published = published
        
def call_flickr_method(method, params):
    return parse("http://api.flickr.com/services/rest/?method="+method+"&api_key="+FLICKR_API_KEY+"&"+params)

def get_user_info_by_url(url):
    result = call_flickr_method("flickr.urls.lookupUser","url="+url)    
    return result

def get_images_from_feed(url):
    images = []
    content = urlfetch.fetch(url).content
    #raise StandardError, content
    dom = minidom.parseString(content)
    
    for entry in dom.getElementsByTagName('entry'):
        photo_id = re.search('.*\/(\d*)\/', entry.getElementsByTagName('id')[0].firstChild.data).group(1) 
        title = entry.getElementsByTagName('title')[0].firstChild.data
        author = entry.getElementsByTagName('name')[0].firstChild.data
        author_url = entry.getElementsByTagName('uri')[0].firstChild.data
        content = entry.getElementsByTagName('content')[0].firstChild.data
        published_str = entry.getElementsByTagName('published')[0].firstChild.data            
        published_date = datetime.datetime(*time.strptime(published_str, "%Y-%m-%dT%H:%M:%SZ")[:6])
        
        image_url = re.search('.*(http:\/\/farm.*_m\.jpg)', content).group(1)
                        
        photo = Photo(photo_id, image_url, title, author, author_url, published_date)
        
        images.insert(0, photo)
            
    return images

def get_image_sizes(photo_id):
    result = call_flickr_method("flickr.photos.getInfo","photo_id="+photo_id)

def parse( url ) :
   result = urlfetch.fetch(url)
   if result.status_code == 200:
       return minidom.parseString(result.content)  
        
 
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
    except KeyError:
        pass
    
    newval['is_admin'] = True #users.is_current_user_admin()
     
#    handler.session = Session()
#        newval['username'] = handler.session['username']
#    if 'username' in handler.session:
                    
    outstr = template.render(temp, newval)
                
    if 'render_to_string' in options:
        return outstr
    else:
        handler.response.out.write(outstr)
        return True 
 
class MainHandler(webapp.RequestHandler):
    def get(self):
        doRender(self, "index.html")
        
class FindUserByUrlHandler(webapp.RequestHandler):
    def get(self):
        info = get_user_info_by_url(self.request.get('url'))
        status = info.getElementsByTagName('rsp')[0].getAttribute('stat')
        
        if status == 'ok':
            user_id = info.getElementsByTagName('user')[0].getAttribute('id')
            user_code = info.getElementsByTagName('username')[0].firstChild.data
        else:
            error_msg = info.getElementsByTagName('err')[0].getAttribute('msg')
            raise StandardError, error_msg
           
        html = ""
        
        contacts = call_flickr_method("flickr.contacts.getPublicList", "user_id="+user_id)
        
        images = []
        for contact in contacts.getElementsByTagName('contact'):
            images.extend(get_images_from_feed("http://api.flickr.com/services/feeds/photos_faves.gne?id="+contact.getAttribute('nsid')))
        
        images.sort(lambda a,b: cmp(a.published,b.published))    
           
        for image_url in [image.image_url for image in images]:
            html += "<img src='"+image_url+"' style='margin: 10px'/>"
        
        self.response.out.write(html)
 
application = webapp.WSGIApplication([
   ('/', MainHandler),
   ('/find_user_by_url', FindUserByUrlHandler)
   ], debug=True)
                
def main():
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            