'''
Created on Nov 11, 2015

@author: derigible

Decorators for methods to determine the authentication/authorization status
of the user.
'''

from functools import wraps

from django.utils.decorators import available_attrs

from mviews.utils import err
from mviews.auth.utils import get_level


def authenticated(func):
    '''
    A decorator to check if the user is authenticated. Since it is undesirable 
    in an api to redirect to a login, this was made to replace the 
    requires_login django decorator. This should be wrapped in method_decorator 
    if a class-based view.
    
    @param func: the view function that needs to have an authenticated user
    @return the response of the function if authenticated, or an error response
    '''
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated():
            return func(request, *args, **kwargs)
        return err("Unauthenticated.", 401)
    return wrapper

def has_level(level):
    '''
    A decorator to check if the user has the correct level to view the object. 
    If not, return a 403 error. Also checks if the user is authenticated
    and return a 401 on false.
    
    @param func: the view function that needs to have proper level
    @param level: the level to check
    @return the response of the function if allowed, or an error response
    '''
    def wrapper(func):
        @wraps(func, assigned=available_attrs(func))
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated():
                return err("Unauthenticated", 401)
            if request.user.level >= get_level(level):
                return func(request, *args, **kwargs)
            return err("Unauthorized. You are not of level {} or above.".format(level), 403)
        return _wrapped
    return wrapper

def has_level_or_is_obj_creator(level):
    '''
    A decorator to check if the user has the correct level to view the object,
    or if user is the creator of the object. If not, will set a flag in the 
    kwargs called _authenticated to False. This flag can be used to determine
    what needs to be done with the unauthenticated user.
     
    Also checks if the user is authenticated and return a 401 on false.
    
    @param func: the view function that needs to have proper level
    @param level: the level to check
    @return the response of the function if allowed, or an error response
    '''
    def wrapper(func):
        @wraps(func, assigned=available_attrs(func))
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated():
                return err("Unauthenticated", 401)
            if request.user.level >= get_level(level):
                return func(request, *args, _authenticated=True, **kwargs)
            return func(request, *args, _authenticated=False, **kwargs)
        return _wrapped
    return wrapper
