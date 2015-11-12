'''
Created on Aug 27, 2015

@author: derigible
'''

from datetime import datetime as dt
from json import loads as load
from json import dumps as d
import math
import os

from django.conf import settings
from django.http.response import JsonResponse as jr


def err(msg, status = 400):
    '''
    Send an error response.
    
    @param msg: the reason for the error
    @param status: the status code of the error
    @return the HttpResponse object
    '''
    resp = jr(d({"err" : "{}".format(msg)}), status = status)
    resp.reason_phrase = msg
    return resp
    
def read(request):
    '''
    Read and decode the payload.
    
    @param request: the request object to read
    @return the decoded request payload
    '''
    d = request.read()
    if d:
        try:
            d = d.decode('utf-8')
            d = load(d)
        except ValueError as e:
            raise ValueError("Not a valid json object: {}".format(e))
    return d
    
def make_new_dir(dir_append = []):
    '''
    Makes a new directory for the current year/month/day and then returns the 
    microsecond for the name of the file. Only makes a new dir if the 
    year/month/day combo does not already exist.
    
    Makes the new path relative to the media root.
    
    @param dir_append: the directory to append to the media root.
    @return the new dir, the new created path, and the ms to create the new file
    '''
    path = [settings.MEDIA_ROOT]
    tstamp = dt.now()
    dir_append
    dir_append.append(str(tstamp.year))
    dir_append.append(str(tstamp.month))
    dir_append.append(str(tstamp.day))
    path += dir_append
    ms = tstamp.microsecond
    path = os.path.join(*path)
    if not os.path.isdir(path):
        os.makedirs(path)
    return path, os.path.join(*dir_append), str(ms)