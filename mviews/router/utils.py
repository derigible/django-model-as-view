'''
Created on Nov 16, 2015

@author: derigible

Defines the utility functions specific to the router package.
'''

from django.http.response import JsonResponse as jr
from django.views.generic.base import View


common_regex = {
                'name' : "[\w|\d|\+|\.]*",
                'url_encoded_name' : "[\w|\d|\+|\.|%|\s|\-|_|=|,|;|(|)|:]*",
                'id' : "\d*",
                'timestamp' : "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+\d{2}:\d{2}",
                'utc_ts' : "\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z"
                }

def check_if_list(lst):
    """
    Since strings are also iterable, this is used to make sure that the 
    iterable is a non-string. Useful to ensure that only lists, tuples, 
    etc. are used and that we don't have problems with strings creeping in.
    """
    if isinstance(lst, str):
        raise TypeError("Must be a non-string iterable: {}".format(lst))
    if not (hasattr(lst, "__getitem__") or hasattr(lst, "__iter__")):
        raise TypeError("Must be an iterable: {}".format(lst))
    
class RoutesOnly(View):
    routes_only = True
    
class Discovery(View):
    """
    Creates a json response that lists all of the available paths for the
    system with their associated regex.
    """
    
    discovery = []
    
    @classmethod
    def add_routes(self, routes):
        for r, doc in routes:
            self.discovery.append({"path" : self._get_path(r), 
                                  "regex" : r, 
                                  "doc" : doc}
                                  )
    
    @classmethod        
    def _get_path(self, r):
        """
        Returns the url_style path with the regex match groups being replaced 
        with {<name>} type endpoints for easy replacement if needed.
        """
        parts = r.split('/')
        out = []
        for p in parts:
            if p == '$':
                continue
            elif p.startswith("(?P<"):
                out.append('{' + p.split('>')[0].split('<')[1] +'}')
            elif p.startswith("([^"):
                out.append("{ids}")
            else:
                out.append(p.lstrip('^')) 
        return '/'.join(out) + '/'
    
    def get(self, request, *args, **kwargs):
        """
        Returns the json object of discovery endpoints. Looks as follows:
        
            {
                "urls" : {
                    "<url_path>" : "<regex of path>"
                }
            }
        """
        return jr({"urls" : self.discovery})