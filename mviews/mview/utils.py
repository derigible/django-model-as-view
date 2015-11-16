'''
Created on Nov 16, 2015

@author: derigible

The utility functions to help set up a response for a modelview.
'''

from django.http.response import HttpResponse

from mviews.errors import AuthenticationError
from mviews.errors import AuthorizationError
from mviews.serializer.serializer import serialize_to_response
from mviews.utils import err

def set_headers(self, response, headers):
        '''
        Set a dictionary of headers to the HttpResponse object.
        
        @param response: the HttpResponse
        @param headers: the headers dictionary
        '''
        for key, val in headers.items():
            setattr(response, key, val)
    
def response(self, qs, headers = {}, extra = None):
    '''
    Returns a response according to the type of request made. This is done 
    by passing in the Accept header with the desired Content-Type. If a 
    recognizable content type is not found, defaults to json. This is a 
    utility for serializing objects.
    
    If the query param single=true is found, then will return a single 
    object if the queryset returns only one object. Otherwise all queries 
    are sent in a list by default. This option is only available for json.
    
    @param request: the request object
    @param qs: an iterable of manager objects, if a string or None will
        return an error response
    @param headers: a dictionary of headers to add
    @param fields: a list of fields to include
    @param extra: any extra data that needs to be serialized
    @return the HttpResponse object
    '''
    if qs is None or isinstance(qs, str):
        if qs is None:
            return err("There was a problem in querying the database"
                       " with the query params provided.")
        else:
            return err(qs)
    resp = serialize_to_response(self, qs, 
                                 rootcall=self.rootcall, 
                                 extra=extra
                                 )
    if headers:
        self.set_headers(resp, headers)
    return resp

def other_response(self, data = None, headers = {}):
    '''
    Returns a response according to the type of request made. This is done 
    by passing in the Accept header with the desired Content-Type. If a 
    recognizable content type is not found, defaults to json. Data should 
    already be formatted in the correct Content-Type. This is a utility for 
    sending all other responses.
    
    @param request: the request object
    @param data: the data to send; if None will send nothing with status 204
    @return the HttpResponse object
    '''
    if data is not None:
        if 'xml' in self.accept:
            ct = "application/xml"
        else: #defaults to json if nothing else is found of appropriate use
            ct = "application/json"
        status = 200
        resp = HttpResponse(data, content_type = ct, status = status)
    else:
        data = ""
        ct = None
        status = 204
        resp = HttpResponse(content_type = ct, status = status)
    if headers:
        self.set_headers(resp, headers)
    return resp

def check_perms(self, request, _perms):
        if hasattr(self, '_perms'):
            if (not request.user.is_authenticated() 
                and request.method.lower() in self._perms):
                raise AuthenticationError()
            req = _perms.get(request.method.lower(), False)
            if req:
                try:
                    if (request.user.level < 
                            request.user.get_level_by_name(req)):
                        raise AuthorizationError("Unauthorized. You do not " 
                                    "have permission "
                                   "'{}' or above.".format(req))
                except AttributeError as e:
                    print(e)
                    pass #Likely because user object not set up or anonymous