import logging
import md5
from xml.dom import minidom
from django.utils import simplejson as json

from google.appengine.api import urlfetch

from lib import demjson

from models import *


FLICKR_API_KEY = 'e5504def2a46e4a654ace751ab1cca88'
FLICKR_SECRET = 'ff8a88e4c4dd7cec'
FLICKR_SIG = '92de0d7a6e1e47839448060a372ceff1' # ff8a88e4c4dd7cecapi_keye5504def2a46e4a654ace751ab1cca88permsread
PIPE_ID = '3417bb5ca134b3571f0b644c48bdc4fe'

FLICKR_AUTH_URL = "http://flickr.com/services/auth/?api_key=%s&perms=read&api_sig=%s" % (FLICKR_API_KEY, FLICKR_SIG)

class FlickrUserInfo:
    def __init__(self, auth_token, userid, username, fullname):
        self.auth_token = auth_token
        self.userid = userid
        self.username = username
        self.fullname = fullname

class FlickrAuthError(StandardError):
    pass

def get_user_info(frob):
    string_for_md5 = "%sapi_key%sfrob%smethodflickr.auth.getToken" % (FLICKR_SECRET, FLICKR_API_KEY, frob)
    logging.info("String for md5: %s" % string_for_md5)    
    api_sig = md5.new(string_for_md5).hexdigest()
    
    logging.info("api_key: %s" % FLICKR_API_KEY)
    logging.info("api_sig: %s" % api_sig)
    logging.info("frob: %s" % frob)
    
    params = "api_key=%s&api_sig=%s&frob=%s" % (FLICKR_API_KEY, api_sig, frob)
    result = call_method("flickr.auth.getToken", params)
    

    if result.getElementsByTagName('err'):
        code = result.getElementsByTagName('err')[0].getAttribute('code')
        msg = result.getElementsByTagName('err')[0].getAttribute('msg')
        
        raise FlickrAuthError, "%s: %s" % (msg,code) 
    
    token    = result.getElementsByTagName('token')[0].firstChild.data
    userid   = result.getElementsByTagName('user')[0].getAttribute('nsid')
    username = result.getElementsByTagName('user')[0].getAttribute('username')
    fullname = result.getElementsByTagName('user')[0].getAttribute('fullname')

    return FlickrUserInfo(token, userid, username, fullname) 

def fetch_and_parse( url ) :
   result = urlfetch.fetch(url)
   if result.status_code == 200:
       return minidom.parseString(result.content)  
        
def call_method(method, params):
    url = "http://api.flickr.com/services/rest/?method="+method+"&api_key="+FLICKR_API_KEY+"&"+params
    
    return fetch_and_parse(url)

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
    return call_method("flickr.photos.getInfo","photo_id="+photo_id)

def get_user_info_by_url(url):    
    info = call_method("flickr.urls.lookupUser","url="+url)
    
    status = info.getElementsByTagName('rsp')[0].getAttribute('stat')
    
    if status == 'ok':
        userid   = info.getElementsByTagName('user')[0].getAttribute('id')
        username = info.getElementsByTagName('username')[0].firstChild.data
    else:
        error_msg = info.getElementsByTagName('err')[0].getAttribute('msg')
        raise StandardError, error_msg
    
    return (userid, username)

def get_contacts_faves(user_key, truncate, page):
    #http://pipes.yahoo.com/pipes/pipe.run?_id=3417bb5ca134b3571f0b644c48bdc4fe&_render=json&truncate=1&user_key=agpmbGlja2ZhdmVychcLEgRVc2VyIg11MTM3NzkyMDZATjA4DA    
    url = "http://files.nixon-site.ru/buger/proxy.php?_id=%s&_render=json&truncate=%s&user_key=%s&page=%s" % (PIPE_ID, truncate, user_key, page)
    #url = "http://pipes.yahoo.com/pipes/pipe.run?_id=%s&_render=json&truncate=%s&user_key=%s&page=%s" % (PIPE_ID, truncate, user_key, page)
    
    result = urlfetch.fetch(url)
    if result.status_code == 200:
        json_object = result.content
        
        photos = demjson.decode(json_object)['value']['items']
        
        return photos        
    else:
        logging.error("Error while updating contacts faves, user_key: %s" % user_key)
        raise StandardError, "Error while updating contacts faves"        
