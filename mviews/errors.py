'''
Created on May 21, 2015

@author: derigible
'''

class BaseAuthError(Exception):
    
    @property
    def status(self):
        raise NotImplementedError("Need to set a status")
        
    def __init__(self, msg):
        super(BaseAuthError, self).__init__(msg)

class AuthenticationError(BaseAuthError):
    
    @BaseAuthError.status.getter
    def status(self):
        return 401
    
    def __init__(self, msg="Authentication error. "
                            "Username/password combination not found."):
        super(AuthenticationError, self).__init__(msg)
        
class AuthorizationError(BaseAuthError):
    
    @BaseAuthError.status.getter
    def status(self):
        return 403
    
    def __init__(self, msg="AuthorizationError error. "
                            "You do not have the correct level "
                            "or you did not create this entity."):
        super(AuthorizationError, self).__init__(msg)