from google.appengine.ext import webapp

import utils
import time

register = webapp.template.create_template_register()

@register.filter
def pretty_date(datetime):
    return utils.pretty_date(datetime)

@register.filter
def image_url_by_layout(photo, layout):
    return photo.image_url_by_layout(layout)