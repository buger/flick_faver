from models import *

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class ContactsHandler(webapp.RequestHandler):
    def get(self, user_key):
        CONTACTS_PER_PAGE = 10
        
        try:
            page = int(self.request.get('page'))
        except ValueError:
            page = 1        
        
        contacts = Contact.gql("WHERE ANCESTOR IS :parent", parent = db.Key(user_key)).fetch(CONTACTS_PER_PAGE, page*CONTACTS_PER_PAGE)
        
        csv = ""
        
        for contact in contacts:
            csv += "%s\n" % (contact.userid)
                    
        self.response.out.write(csv)


application = webapp.WSGIApplication([
   ('/api/contacts/([^\/]*)', ContactsHandler)
   ], debug=True)
                
def main():
    run_wsgi_app(application)
 
if __name__ == '__main__':
    main()            