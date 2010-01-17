import logging
import md5
import urllib
from xml.dom import minidom
from django.utils import simplejson as json

from google.appengine.api import urlfetch

from lib import demjson

from models import *


FLICKR_API_KEY = 'e5504def2a46e4a654ace751ab1cca88'
#FLICKR_API_KEY = 'e6929d1308546d366dad4a9d36901c6b'

FLICKR_SECRET = 'ff8a88e4c4dd7cec'
#FLICKR_SECRET = '567ec3c72f27c571'

FLICKR_SIG = '18b46b4ceb730cbaac5a8de4d2d81712' # ff8a88e4c4dd7cecapi_keye5504def2a46e4a654ace751ab1cca88permswrite
#FLICKR_SIG = '47a4dad57755a116205701c76030215c'

FLICKR_AUTH_URL = "http://flickr.com/services/auth/?api_key=%s&perms=write&api_sig=%s" % (FLICKR_API_KEY, FLICKR_SIG)

class FlickrUserInfo:
    def __init__(self, auth_token, userid, username, fullname):
        self.token = auth_token
        self.nsid = userid
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
    
    params = {'api_key':FLICKR_API_KEY,
              'api_sig':api_sig,
              'frob':frob}
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
   
   logging.info(result.content)
   
   if result.status_code == 200:
       return minidom.parseString(result.content)  

def dict_sorted_by_key(dict):
    return sorted(dict.items(), lambda x,y: cmp(x[0],y[0]))

def dict_to_query_string(dict = {}):    
    return '&'.join([k+'='+urllib.quote(str(v)) for (k,v) in dict_sorted_by_key(dict)])

def dict_to_string(dict = {}):
    return ''.join([k+''+urllib.quote(str(v)) for (k,v) in  dict_sorted_by_key(dict)])

def token_signature(token, method, params):    
    string_for_md5 = "%sapi_key%sauth_token%smethod%s%s" % (FLICKR_SECRET, FLICKR_API_KEY, token, method, dict_to_string(params))
    
    logging.warning(string_for_md5)
    
    return md5.new(string_for_md5).hexdigest() 

def call_method(method, params, token = None):
    if token:               
        params['api_sig'] = token_signature(token, method, params)        
        params['auth_token'] = token
            
    url = "http://api.flickr.com/services/rest/?method="+method+"&api_key="+FLICKR_API_KEY+"&"+dict_to_query_string(params)
    logging.info("Calling method. Url: %s" % url)
    
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
    return call_method("flickr.photos.getInfo", {'photo_id':photo_id})

def get_user_info_by_url(url):    
    info = call_method("flickr.urls.lookupUser",{'url':url})
    
    status = info.getElementsByTagName('rsp')[0].getAttribute('stat')
    
    if status == 'ok':
        userid   = info.getElementsByTagName('user')[0].getAttribute('id')
        username = info.getElementsByTagName('username')[0].firstChild.data
    else:
        error_msg = info.getElementsByTagName('err')[0].getAttribute('msg')
        raise StandardError, error_msg
    
    return (userid, username)


PHOTOS_PER_CONTACT = 20

def get_faves(nsid, per_page = PHOTOS_PER_CONTACT):    
    photos_xml = call_method("flickr.favorites.getPublicList",
                             {'user_id' :nsid,
                              'extras'  :'url_m,path_alias,owner_name',
                              'per_page':per_page})

    return photos_xml.getElementsByTagName('photo')


CONTACTS_PER_PAGE = 5

def get_contacts(nsid = None, page = 1, token = None):
    '''Returns contacts in raw XML'''    
    
    params = {'page':page, 'per_page':CONTACTS_PER_PAGE}
    
    if token is None:
        method = "flickr.contacts.getPublicList"
        params['user_id'] = nsid
    else:
        method = "flickr.contacts.getList"
        
    response = call_method(method, params, token)
    
    contacts_root_xml = response.getElementsByTagName('contacts')[0]
    
    pages = int(contacts_root_xml.getAttribute('pages'))    
    contacts  = response.getElementsByTagName('contact')
    
    return (contacts, pages)
            


ICON_URL_FORMAT = "http://farm%s.static.flickr.com/%s/buddyicons/%s.jpg"

def icon_url(farm = None, server = None, nsid = None):
    '''Returns user icon url'''
    
    if farm is None or server is None or nsid is None:    
        raise StandardError, "Can't generate icon_url. Not enough data." 
    
    return ICON_URL_FORMAT % (farm, server, nsid)    


PHOTO_URL_FORMAT = "http://www.flickr.com/photos/%s/%s"

def photo_uri(user, photo_id):
    return "http://www.flickr.com/photos/%s/%s" % (user, photo_id)

def original_image_url(photo_id, token):
    result = call_method('flickr.photos.getSizes', {'photo_id':photo_id}, token)
    
    for size in result.getElementsByTagName('size'):        
        if size.getAttribute('label') == 'Original' or size.getAttribute('label') == 'Large':
            return size.getAttribute('source')
    
    return None
    
def favorite(photo_id, token):
    result = call_method('flickr.favorites.add', {'photo_id':photo_id}, token)
    
    if result.getElementsByTagName('rsp')[0].getAttribute('stat') == 'ok':
        return "success"
    else:
        error = result.getElementsByTagName('err')[0]
        
        if error.getAttribute('code') == '3':
            return "success"
        else:
            return error.getAttribute('msg')
    
def remove_favorite(photo_id, token):
    result = call_method('flickr.favorites.remove', {'photo_id':photo_id}, token)
    
    if result.getElementsByTagName('rsp')[0].getAttribute('stat') == 'ok':
        return "success"
    else:
        return result.getElementsByTagName('err')[0].getAttribute('msg')
        

USER_URL_FORMAT = "http://www.flickr.com/photos/%s" 

def user_uri(user):
    return USER_URL_FORMAT % user