'''
Created on Mar 12, 2015
@author: derigible
'''

import importlib as il
import inspect
import pkgutil
import sys

from django.conf.urls import patterns
from django.conf.urls import url
from django.conf import settings
from django.views.generic.base import View

from .utils import check_if_list
from .utils import Discovery


class Routes(object):
    '''
    A way of keeping track of routes at the view level instead of trying to 
    define them all inside the urls.py. The hope is to make it very 
    straightforward and easy without having to resort to a lot of custom 
    routing code. This will be accomplished by writing routes to a list and 
    ensuring each pattern is unique. It will then add any pattern mappings
    to the route for creation of named variables. An optional ROUTE_AUTO_CREATE 
    setting can be added in project settings that will create a route for every 
    app/controller/view and add it to the urls.py.
    
    It also will create an endpoint at /discovery/ that shows all of the
    registered routes and any docs that are associated with them.
    '''
    #Class instance so that lazy_routes will add to the routes 
    #table without having to add from the LazyRoutes list.
    routes = []
    #to be used to make the discovery endpoint after routes are created
    discovery = [] 
    acceptable_routes = ('app_module_view', 'module_view')
    tracked = set() #single definitive source of all routes
    
    def __init__(self, project_name=None):
        '''
        Initialiaze the routes object by creating a set that keeps track of all 
        unformatted strings to ensure uniqueness.
        '''
        #Check if the urls.py has been loaded, and if not, then load it (for 
        #times when you want to create the urls without loading Django 
        #completely)
        if project_name is not None:
            proj_name_urls = project_name + '.urls'
            if proj_name_urls not in sys.modules:
                try:
                    il.import_module(proj_name_urls)
                except ImportError as e:
                    print("passing on loading urls: {}".format(e))
        if hasattr(settings, "ROUTE_AUTO_CREATE"):
            if settings.ROUTE_AUTO_CREATE == "app_module_view":
                self._register_installed_apps_views(settings.INSTALLED_APPS, 
                                                    with_app=True)
            elif settings.ROUTE_AUTO_CREATE == "module_view":
                self._register_installed_apps_views(settings.INSTALLED_APPS)
            else:
                raise ValueError("The route_auto_create option was set in "
                                 "settings but option {} is not a valid "
                                 "option. Valid options are: {}"
                                 .format(settings.route_auto_create, 
                                         self.acceptable_routes
                                         )
                                 )
    
    def _register_installed_apps_views(self, apps, with_app = False):
        '''
        Set the routes for all of the installed apps (except the django.* 
        installed apps). Will search through each module in the installed app 
        and will look for a view class. If a views.py module is found, any 
        functions found in the  module will also be given a routing table by 
        default. Each route will, by default, be of the value 
        <module_name>.<view_name>. 
        
        If you are worried about view names overlapping between apps, then use 
        the with_app flag set to true and routes will be of the variety of 
        <app_name>.<module_name>.<view_name>. The path after the base route 
        will provide positional arguments to the url class for anything between 
        the forward slashes (ie. /). For example, say you have view inside 
        a module called foo, your route table would include a route as follows:
        
            ^foo/view_name/(?([^/]*)/)*
        
        Note that view functions that are not class-based must be included in 
        the top-level directory of an app in a file called views.py if they are 
        to be included. This does not make use of the Django app loader, so it 
        is safe to put views in files outside of the views.py, as long as 
        those views are class-based.
        
        Note that class-based views must also not require any parameters in the 
        initialization of the view.
        
        To prevent select views from being registered in this manner, set 
        the register_route variable on the view to False.
        
        All functions within a views.py module are also added with this view. 
        That means that any decorators will also have their own views. If this 
        is not desired behavior, then set the settings.REGISTER_VIEWS_PY_FUNCS 
        to False.
            
        @param apps: the INSTALLED_APPS setting in the settings for your Django 
                    app.
        @param with_app: set to true if you want the app name to be included 
                        in the route
        '''
        def add_func(app, mod, funcName, func):
            r = "{}/{}/([^\s#?]*)".format(mod,funcName)
            if with_app:
                r = "{}/{}".format(app, r.lstrip('/'))
            self.add(r.lower(), func, add_ending=False)
            
        def load_views(mod, mod_name, parent_mod_name = ""):
            if parent_mod_name:
                name_mod = parent_mod_name + '/' + mod_name
            else:
                name_mod = mod_name
            for klass in inspect.getmembers(mod, inspect.isclass):
                #only add those views defined in the module
                if mod.__name__ != klass[1].__module__:
                    continue
                try:
                    try:
                        inst = klass[1]()
                    except AttributeError:
                        continue #object is perhaps a model object
                    #we do not want to add the View class
                    if isinstance(inst, View): 
                        if (
                            (not hasattr(inst, 'register_route') 
                             or (hasattr(inst, 'register_route') 
                             and inst.register_route)
                            )
                            and not getattr(inst, 'routes_only', False)
                            ):
                            add_func(app, 
                                     name_mod, 
                                     klass[0], 
                                     klass[1].as_view()
                                     )
                        if hasattr(inst, 'routes'):
                            self.add_view(klass[1])
                except TypeError as e: #not a View class if init requires input.
                    if "'function' object is not subscriptable" in str(e):
                        raise ValueError("Attempting to do something wrong")
                    if 'string indices must be integers' in str(e):
                        raise TypeError from e
                except ValueError as e:
                    print(e)
            if (mod_name == "views" 
                and (hasattr(settings, 'REGISTER_VIEWS_PY_FUNCS')                       
                and settings.REGISTER_VIEWS_PY_FUNCS)
                ):
                for func in inspect.getmembers(mod, inspect.isfunction):
                    add_func(app, name_mod, func[0], func[1])
        
        def load_module(mod, pkg, path = ""):
            '''
            Load the module and get all of the modules in it.
            '''
            print("The module and pkg of the load_module:",mod, pkg, path)
            loaded_app = il.import_module('.' + mod, pkg)
            for finder, mname, ispkg in pkgutil.walk_packages([loaded_app
                                                               .__path__[0]
                                                               ]
                                                              ):
                if ispkg:
                    load_module(mname, loaded_app.__package__, path+'/'+mod)
                views_mod = il.import_module('.' + mname, 
                                             loaded_app.__package__
                                             )
                #Check if the module itself has any view classes
                load_views(views_mod, mname, path + '/' + mod) 
            
        for app in settings.INSTALLED_APPS:
            if 'django' != app.split('.')[0]: #only do it for non-django apps
                loaded_app = il.import_module(app)
                for finder, mname, ispkg in pkgutil.walk_packages([loaded_app
                                                                   .__path__[0]
                                                                   ]
                                                                  ):
                    if ispkg:
                        load_module(mname, loaded_app.__package__)
                    else:
                        mod = il.import_module('.' + mname, 
                                               loaded_app.__package__
                                               )
                        load_views(mod, mname)
                        
    def add(self, route, func, var_mappings= None, add_ending=True, **kwargs):
        '''
        Add the name of the route, the value of the route as a unformatted 
        string where the route looks like the following:
        
        /app/{var1}/controller/{var2}
        
        where var1 and var2 are arbitrary place-holders for the var_mappings. 
        The var_mappings is a list of an iterable of values that match the 
        order of the format string passed in. If no var_mappings is passed in 
        it is assumed that the route has no mappings and will be left as is.
        
        Unformatted strings must be unique. Any unformatted string that is 
        added twice will raise an error.
        
        To pass in a reverse url name lookup, you can use the key word 
        'django_url_name' in the kwargs dictionary.
        
        @param route: the unformatted string for the route
        @param func: the view function to be called
        @param var_mappings: the list of dictionaries used to fill in the var 
                            mappings
        @param add_ending: adds the appropriate /$ is on the ending if True. 
                    Defaults to True
        @param kwargs: the kwargs to be passed into the urls function
        '''
        self._check_if_format_exists(route)
        
        def add_url(pattern, pmap, ending, opts):
            url_route = '^{}{}'.format(pattern.format(*pmap), 
                                       '/$' if ending else ''
                                       )
            if "django_url_name" in opts:
                url_obj = url(url_route, 
                              func, 
                              kwargs, 
                              name=kwargs['django_url_name']
                              )
            else:
                url_obj = url(url_route, func, kwargs)
            self.routes.append(url_obj)
            self.discovery.append((url_route, func.__doc__))
            
        if var_mappings:
            for mapr in var_mappings:
                check_if_list(mapr)
                add_url(route, mapr, add_ending, kwargs)
        else:
            add_url(route, [], add_ending, kwargs)
    
    def add_list(self, routes, func, prefix=None, **kwargs):
        '''
        Convenience method to add a list of routes for a func. You may pass in 
        a prefix to add to each pattern. 
        
        For example, each url needs the word workload prefixed to the url 
        to make: workload/<pattern>.
        
        Note that the prefix should have no trailing slash.
        
        A route table is a dictionary after the following fashion:
        
        {
         "pattern" : <pattern>', 
         "map" :[['<regex_pattern>',...], ...],
         "kwargs" : dict
        }
        
        @param routes: the list of routes
        @param func: the function to be called
        @param prefix: the prefix to attach to the route pattern
        '''
        check_if_list(routes)
        for route in routes:
            route_kwargs = kwargs.copy()
            if 'kwargs' in route:
                if type(route['kwargs']) != dict:
                    raise TypeError("Must pass in a dictionary for kwargs.")
                for k, v in route["kwargs"].items():
                    route_kwargs[k] = v
            self.add(route["pattern"] if prefix is None 
                                      else '{}/{}'.format(prefix, 
                                                          route["pattern"]
                                                          ),
                      func, 
                      var_mappings= route.get("map", []), 
                      **route_kwargs
                      )
    
    @property
    def urls(self):
        '''
        Get the urls from the Routes object. This a patterns object.
        '''
        Discovery.add_routes(self.discovery)
        self.add('discovery', Discovery.as_view())
        return patterns(r'',*self.routes)
        
    def _check_if_format_exists(self, route):
        '''
        Checks if the unformatted route already exists.
        
        @route the unformatted route being added.
        '''
        if route in self.tracked:
            raise ValueError("Cannot have duplicates of unformatted routes: {} "
                                "already exists.".format(route)
                                )
        else:
            self.tracked.add(route)
            
    def add_view(self, view, **kwargs):
        '''
        Add a class-based view to the routes table. A view that is added to the 
        routes table must define the routes table; ie:
        
            (
                  {"pattern" : <pattern>', 
                   "map" :[('<regex_pattern>',), ...],
                   "kwargs" : dict
                   },
                 ...
            )
        
        Kwargs can be ommitted if not necessary.
        
        Optionally, if the view should have a prefix, then define the variable 
        prefix as a string; ie
        
            prefix = 'workload'
            
            or
            
            prefix = 'workload/create
            
        Note that the prefix should have no trailing slash.
        
        If you want to remove the add_ending option, then set add_ending 
        variable to False on the view.
        
        @view the view to add
        '''
        if not hasattr(view, 'routes'):
            raise AttributeError("routes variable not defined on view {}"
                                 .format(view.__name__)
                                 )
        if hasattr(view, 'prefix'):
            prefix = view.prefix
        else:
            prefix = None
        if hasattr(view, 'add_ending') and 'add_ending' not in kwargs:
            kwargs['add_ending'] = view.add_ending
        
        self.add_list(view.routes, view.as_view(), prefix = prefix, **kwargs)

class LazyRoutes(Routes):
    '''
    A lazy implementation of routes. This means that LazyRoutes won't add 
    routes to the Routes table until after the routes table has been created. 
    This is necessary when the ROUTE_AUTO_CREATE setting is added to the Django 
    settings.py.
    
    All defined routes using the routes.* method must now become lazy_routes.* 
    methods.
    '''
    
    def __init__(self):
        '''
        Do nothing, just overriding the base __init__ to prevent the 
        initialization there.
        '''
        pass
        
lazy_routes = LazyRoutes()
routes = Routes()