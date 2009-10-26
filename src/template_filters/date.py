from google.appengine.ext import webapp

import utils
import time

register = webapp.template.create_template_register()

@register.filter
def pretty_date(datetime):
    return utils.pretty_date(datetime)