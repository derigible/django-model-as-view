'''
Created on Nov 11, 2015

@author: derigible

Since the user model will change locations and names with each app, it is 
necessary to describe a common interface to access the user model.

Defines the utility functions to be used in the auth framework of the mviews
framework. All functions that get the user model should access it through this
module.
'''

from django.contrib.auth import authenticate as auth
from django.contrib.auth import get_user_model
from django.contrib.auth import login
from django.contrib.auth import SESSION_KEY

from mviews.utils import read
from mviews.errors import AuthenticationError


USER = get_user_model


def get_user_level_names():
    """
    Get the user levels that are currently defined on the user model. An attribute
    error is raised if the level_by_name dictionary is not defined.
    
    The level_by_name dictionary should look as follows:
    
        level_by_name = {
                          "level1" : 0,
                          "level2" : 1
                        }
    
    @return the current user model levels_by_name dictionary 
    """
    return USER().level_by_name

def get_user_levels():
    """
    Get the user levels as defined by the user model. An attribute error is
    raised if the levels dictionary is not defined.
    
    The levels dictionary should look as follows:
    
        levels = {
                      0 : "student",
                      1 : "teacher"
                  }
    
    @return the current user model levels dictionary
    """
    return USER().levels

def get_level_name(level):
    """
    Gets the user level name.
    
    @param level: the int of the level
    @return the level name
    """
    return get_user_level_names()[level]

def get_level(levelName):
    """
    Gets the user level by the name.
    
    @param levelName: the name of the level
    @return the level int
    """
    return get_user_levels()[levelName]

def authenticate(request, email = None, password = None):
    '''
    Log the Poster in or raise an Unauthenticated error. If email or password 
    is None, will attempt to extract from the request object. This assumes it 
    is a json object. If other formats are used, you must pass in email and 
    password separately. The user object will be placed in the request object 
    after successful login.
    
    @param request: the request to log in
    @param email: the email of the poster
    @param password: the password of the poster
    @return the sessionid, the user object
    '''
    if email is None or password is None:
        try:
            j = read(request)
            email = j["email"]
            password = j["password"]
        except ValueError:
            raise ValueError("Faulty json. Could not parse.")
        except KeyError as ke:
            KeyError(ke)
    user = auth(username = email, password = password)
    if user is None:
        raise AuthenticationError()
    login(request, user)
    return request.session[SESSION_KEY]