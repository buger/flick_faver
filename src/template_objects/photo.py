'''
Created on 04.12.2009

@author: buger
'''

# For templates, using in tag clouds
class PhotoTeplateObject:
    def __init__(self, photo_id, image_url, title, author, author_url, published):
        self.photo_id = photo_id
        self.image_url = image_url
        self.title = title
        self.author = author
        self.author_url = author_url
        self.published = published