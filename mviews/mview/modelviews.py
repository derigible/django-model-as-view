"""
Created on Jul 2, 2015

@author: derigible

An attempt to combine views with a manager without having to write any extra
code. This is to make writing REST applications much simpler as it will
treat each table as if it is a returnable entity. The beauty of this setup
is that since it is a Django manager it can still be referenced by other 
Django models. This only adds some automatic support to the manager, nothing
more.

NOTE: By using this class you need to read all the documentation on it.
"""

from json import dumps

from django.contrib.auth.models import BaseUserManager
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Avg
from django.db.models import Max
from django.db.models import Min
from django.db import models as m
from django.db import transaction
from django.views.generic.base import View
from django.http.response import HttpResponse
from django.contrib.auth.models import AbstractBaseUser
from django.conf import settings
from django.utils import timezone

from .utils import check_perms
from .utils import response
from .utils import other_response
from mviews.utils import err
from mviews.utils import read
from mviews.errors import BaseAuthError

class ViewWrapper(View):
    """
    A wrapper to ensure that the view class never gets positional arguments so
    as to make it work with being combined with Models.
    
    All methods are allowed on an endpoint by default. To turn off a method,
    simply change the allowed methods here.
    
    Authorization is also handeld here if the perms dictionary is added to a
    model. This dictionary (called _perms) is of the following format:
    
    {
        "<method>" : "<required perm>",
        "<method2>" : "<required perm>"
    }
    
    You must also fill out the get_level_by_name dictionary on the user object
    for this to work. If either of the dictionaries is not found, authorization
    checks will be skipped. User perms must also be linked to a level and the 
    get_level_by_name should assign those perms to a number. The user object
    must also have a level attribute. To assist in making a user object, use 
    the UserModelAsView class for your user model, or extend the ABUWrapper
    and the UserManagerWrapper(if needed) to implement your users. Then
    be sure to set the AUTH_USER_MODEL = '<your user>' in your settings
    (see https://docs.djangoproject.com/en/1.8/topics/auth/customizing/#extending-the-existing-user-model
    for more details).
    
    NOTE: If a permission is not in the _perms dictionary it is assumed safe
    for anyone logged in. If you want to override the behavior and set it safe
    for anyone if method is not set, then override the _check_perms method.
    """
    allowed_methods = ['get', 'post', 'put', 'delete', 'head', 'options']
    return_types = ['application/json']
    parses = ['application/json']

    def __init__(self, *args, **kwargs):
        super(ViewWrapper, self).__init__(**kwargs)
        
    def dispatch(self, request, *args, **kwargs):
        if request.method.lower() not in self.allowed_methods:
            return err("Method {} not allowed.".format(request.method), 405)

        try:
            check_perms(request, getattr(self, '_perms', {}))
        except BaseAuthError as e:
            return err(e, e.status)
        #It makes sense why these are stored in the request, but i want them
        #in the view for convenience purposes
        self.accept = request.META.get('HTTP_ACCEPT', 'application/json')
        self.params = request.GET
        self.params._mutable = True #no reason for it to stay immutable
        self.fields = [f for f in self.params.get('_fields', "").split(',') 
                       if f in self.field_names]
        
        self.sdepth = (int(self.params['_depth']) 
                       if self.params.get('_depth', None) is not None and 
                       self.params.get('_depth', None).isdigit() else 0)
        if not self.sdepth:
            if hasattr(self, 'expand') or '_expand' in self.params:
                self.sdepth = 1
        if getattr(settings, 'HYPERLINK_VALUES', True):
            self.rootcall = request.scheme + '://' + request.get_host()
        else:
            self.rootcall = ''
        try:
            self.data = read(request)
        except ValueError as e:
            return err(e)
        return super(ViewWrapper, self).dispatch(request, *args, **kwargs)

class BaseModelWrapper():
    """
    A wrapper to help define what a model wrapper will need. This is necessary
    since the AbstractBaseUser model is a model already and you can't sublass
    from two models. Or something like that.
    """
    
    def delete_entity(self, *args, **kwargs):
        raise NotImplementedError("This had not been implemented.")
    
class ModelWrapper(BaseModelWrapper, m.Model):
    """
    A wrapper to ensure that the model class does not get called when a DELETE
    method is sent. To delete a model, call the delete_entity method.
    """
#TODO put in some base model validation when the __new__ is called
    
    def delete_entity(self, *args, **kwargs):
        """
        Call this method to delete a model instance.
        """
        super(ModelWrapper, self).delete(*args, **kwargs)
        
    class Meta:
        abstract = True
        
class UserManagerWrapper(BaseUserManager):
    
    def _create_user(self, username, 
                     email, 
                     password,
                     is_staff, 
                     is_superuser, 
                     **extra_fields
                     ):
        """
        Creates and saves a User with the given username, email and password.
        """
        now = timezone.now()
        if not username:
            raise ValueError('The given username must be set')
        email = self.normalize_email(email)
        user = self.model(username=username, email=email,
                          is_staff=is_staff, is_active=True,
                          is_superuser=is_superuser,
                          date_joined=now, **extra_fields)
        user.level = 1
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, date_of_birth, password):
        """
        Creates and saves a superuser with the given email and password.
        """
        user = self.create_user(email, password=password)
        user.level = 5
        user.save(using=self._db)
        return user
            
class ABUWrapper(BaseModelWrapper, AbstractBaseUser):
    """
    A wrapper to ensure that the user model does not get called when a DELETE
    method is sent. To delete a user, call the delete_entity method.
    """
    level = m.SmallIntegerField('The level of the user.', default = 0)
    objects = UserManagerWrapper() 
    
    def delete_entity(self, *args, **kwargs):
        """
        Call this method to delete a model instance.
        """
        super(ABUWrapper, self).delete(*args, **kwargs)
        
    class Meta:
        abstract = True

class BaseModelAsView(BaseModelWrapper, ViewWrapper):
    """
    A base class should inherit this first, then a Modelwrapper, than a
    ViewWrapper.
    
    A few things to note about this class:
        
    To send in a page, use the _page query param. You can also set the default
    pagination size by adding the __paginate attribute to the model view, which
    will be used if the _limit query param is not found.
    
    To set a custom limit on the pagination, use the query param _limit.
        -Note: negative numbers are not valid and will default to 10
        
    When the unique id you want to query by is not the pk of the field, you can
    add the _unique_id = '<field>' on the model, where field is the name of the 
    field you want to query by.
    """
    
    @property
    def unique_id(self):
        if not hasattr(self, '_unique_id'):
            self._unique_id = self._meta.pk.name       
        return self._unique_id
    
    @property
    def url_path(self):
        """
        Get the url path for this modelview.
        """
        if not hasattr(self, '_url_path'):
            if settings.ROUTE_AUTO_CREATE == 'app_module_view':
                p = '/'.join(self.__module__.split('.') )
            else:
                p = self.__module__.split('.')[-1]
            self._url_path = (p +
                               '/' + 
                              self.__class__.__name__.lower())
        return self._url_path
    
    @property
    def m2ms(self):
        if not hasattr(self, "_m2ms"):
            self._m2ms = [str(m2m[0]).split('.')[-1] 
                           for m2m in self.__class__._meta.get_m2m_with_model()
                         ]
        return self._m2ms
    
    @property
    def fks(self):
        if not hasattr(self, "_fks"):
            self._fks = [str(fk).split('.')[-1] for fk in self.field_names 
                         if getattr(self.__class__._meta.get_field_by_name(fk)[0], 
                                    "rel",
                                     False
                                     ) 
                            and not fk.endswith('_id')
                         ]
        return self._fks
        
    @property
    def field_names(self):
        if not hasattr(self, "_field_names"):
            self._field_names = getattr(self, 'public_fields', False)
            if not self._field_names:
                self._field_names = self.__class__._meta.get_all_field_names()
        return self._field_names
     
    def _get_ids_from_args(self, *args):
        '''
        Get the ids from the arguments or from the ids param if it exists, or
        return an empty list if none are found.
        ''' 
        if not args:
            return args
        if args[0] is not None and args[0]:
            args = args[0].strip('/')
            args = args.split('/')
        else:
            args = []
        if "ids" in self.params:
            args += self.params.get('ids').split(',')
        return args   
        
    def _get_qs(self, *args, **kwargs):
        '''
        A helper method to get the queryset, to be used for GET, PUT, and maybe
        DELETE. Look at the GET docs to see how this works.
        '''
        def filter_by_pks(vals):
            for f in self.field_names:
                if getattr(self._meta.get_field_by_name(f)[0], 
                           "primary_key", 
                           False):
                    return {f + "__in" : vals}
            else:
                return {}
        
        args = self._get_ids_from_args(*args)
        try:
            filtered = self.__class__.objects.all()
        except AttributeError:
            raise TypeError("This model is abstract and has no actual data "
                            "fields.")
        if len(args) == 1 and 'id' in self.field_names:
            filtered = filtered.filter(id = args[0])
        elif 'id' in self.field_names and args:
            filtered = filtered.filter(id__in = args)
        elif args:
            filtered = filtered.filter(**filter_by_pks(args))            
        reqDict = {field : self.params[field] for field in self.field_names 
                                                  if field in self.params
                                                  } 
        return filtered.filter(**reqDict)
    
    def _expand(self, qs):
        '''
        Expands the queryset if necessary.
        '''
        pfields = getattr(self, 'public_fields', [])
        fields = []
        if self.fields or pfields:
            if pfields and not self.fields:
                fields = pfields
            else:
                fields = self.fields #already filtered
        if self.sdepth:
            if fields:
                qs = qs.only(*fields)
            qs = qs.select_related(*self.fks).prefetch_related()
        elif fields:
            qs = qs.values(*fields)
        else:
            qs = qs.values()
        return qs
    
    def _get_aggs(self, qs):
        aggers = {}
        if '_aggs' not in self.params:
            return qs
        if '_aggs_only' in self.params:
            qs = qs.only()
        aggs = self.params['_aggs'].split(',')
  
        for agg in aggs:
            try:
                ag, f = agg.split(' ')
            except ValueError:
                ag, f = agg.split('+')
            if ag not in ('max', 'min', 'avg') or f not in self.field_names:
                continue
            if ag == "max":
                aggers["max_{}".format(f)] = Max(f)
            elif ag == "min":
                aggers["min_{}".format(f)] = Min(f)
            elif ag == "avg":
                aggers["avg_{}".format(f)] = Avg(f)
        qs = qs.annotate(**aggers)
        return qs
    
    def do_get(self, request, *args, **kwargs):
        '''
        Will do a get without returning a response, but instead returns the
        list of objects that can be serialized by the serializer. Useful if
        you want the GET functionality but need to do some transforms on the
        output before sending. This is a method to override GET without
        rewriting everything.
        
        Look at get for more info on how this is to be used.
        
        @return an iterable of values from the database, not necessarily of 
        model objects
        '''
        try:
            qs = self._expand(self._get_qs(*args, **kwargs))
        except ValueError as e:
            return err(e, 500)
        qs = self._get_aggs(qs)
        if 'latest' in self.params:
            qs = [qs[0]]
        return qs
    
    def get(self, request, *args, **kwargs):
        '''
        If args is empty, returns all entities. Otherwise, the args can come 
        in two formats:
        
            1) the first arg in the path (passed in as a path variable) is an 
                id of the entity
                a) filter args need to be passed in as query params
            2) add as many ids as you can in the path in this manner: /1/2/4/.../ 
            3) add the query param ids as a csv for those entities by id 
                you want: ids=1,2,3,4,...
                
        Note that the query params need to match the name of the manager 
        fields in order to work.
        
        You may also pass in other filtering criteria by adding the key,value 
        pair of a field you wish to filter on. For example:
        
            name=Bob
            
        If there is a name field on the entity, will filter by the name Bob. 
        Adding fields  that are not present on the entity does nothing. If you
        pass in the filter name=Bob and no ids, will search only on that field. 
        
        A query with no filter will return the entirety of that entity's table. 
        If you pass in the keyword _expand, will get the objects related to 
        this entity as well and place them in the corresponding entity's object
        under a list with the name of the m2m field as identifier.
        
        If the query _fields is passed in as a csv of desired fields, will 
        attempt to retrieve only those fields requested, otherwise all fields 
        are returned.
        
        If you add the keyword _aggs to the query with the values being a csv
        of key value pairs with the agg on the left and the field on the right,
        it will return those aggs alongside the qs. Example:
        
            _aggs=avg+<field_name>,min+<field_name>...
            
        If you want to return only the aggregates and not the rest of the query,
        set the flag _aggs_only.
        '''
        return response(self, self.do_get(request, *args, **kwargs))
    
    def do_post(self, request, *args, **kwargs):
        '''
        Because there are times when the output from the post may need to be
        modified or used before sending, the option to take advantage of the
        built-in behavior of a post without returning a response is provided.
        
        See the post doc for more info about how this is used.
        
        @return a list-like structure of model objects that can be serialized
        '''
        user_field_name = getattr(self, 'register_user_on_create', '')
        if isinstance(self.data["data"], dict):
            if user_field_name:
                self.data["data"][user_field_name] = request.user
            bp = self.__class__.objects.create(**self.data["data"])
            if len(self.data) > 1: #there are many2many fields to add, lets add them
                for m2m in self.m2ms:
                    if m2m in self.data and type(self.data.get(m2m)) == list:
                        getattr(bp, m2m).add(*self.data[m2m])
            self.sdepth = 1
            return (bp,)
        else:
            to_create = []
            if user_field_name:
                for ud in self.data["data"]:
                    ud[user_field_name] = request.user
                    to_create.append(self.__class__(**ud))
            else:
                to_create = [self.__class__(**ud) for ud in self.data["data"]]
            if self.sdepth:
                for c in to_create:
                    c.save()
                return to_create
            else:
                created = self.__class__.objects.bulk_create(to_create)
                self.sdepth = 1
                return created   
    
    def post(self, request, *args, **kwargs):
        '''
        The post currently only accepts json. Json generically looks like:
        
        {  
            "data" : {
                "<data_field_name>" : "<data>" | <data>, ...
            },
            "<m2m>" : [
                <m2m_id>,...
            ]
        }
        
        If your model requires that the user is registered on create, then
        add the register_user_on_create = <user_model_field_name> where the
        value is the name of the field the user model is in. 
        
        To create multiple entities at once, send data as follows:
        
        {
            "data" : [
                {
                    "<data_field_name>" : "<data>" | <data>, ...
                }, ...
            ]
        }
        
        This method will allow for an efficient and fast means of creating
        all of the entities in one batch save. However, there may be times
        when you want to save m2m fields with the data, or perhaps you
        want a return value of the newly created entity with the entity's id
        in the database. Currently the above method does not return the new
        entity's id. To do this, send data as follows while adding the
        '_expand' query param:
        
        {
            "data" : [
                {
                    "entity" : {
                        "<data_field_name>" : "<data>" | <data>, ...
                        },
                    "<m2m>" : [
                        <m2m_id>,...
                    ]
                }, ...
            ]
        }
        
        These will return the data that has been created as if it were a GET.
        '''
        return response(self, self.do_post(request, *args, **kwargs))   
    
    def _update_entity(self, qs, data, to_remove):
        """
        Updates the entity
        """
        if to_remove is not None:
            to_remove += ['id']
            for tr in to_remove:
                if tr in self.data["data"]:
                    del self.data["data"][tr]
        qs.update(**data['data'])
        if len(self.data) > 1: #there are many2many fields to add and delete, lets add them
            for m2m in self.m2ms:
                if m2m in self.data:
                    if ("add" in self.data[m2m] and 
                            type(self.data[m2m]['add']) == list):
                        getattr(qs[0], m2m).add(*self.data[m2m]['add'])
                    if ("delete" in self.data[m2m] and 
                            type(self.data[m2m]['delete']) == list):
                        getattr(qs[0], m2m).remove(*self.data[m2m]['delete'])
    
    def do_put(self, request, *args, **kwargs):
        '''
        Do the put but return the output before sending a response. Useful
        for subclassing the put method.
        
        See put for how this method is used.
        
        To prevent certain fields from being updated, add them to the 
        _no_update_fields list. The id field is added by default. To prevent
        all data from being updated, set _no_update_fields to None.
        '''
        to_remove = getattr(self, '_no_update_fields', []) 
        if not isinstance(self.data['data'], list):
            qs = self._get_qs(*args, **kwargs)
            self._update_entity(qs, self.data, to_remove)
        else:
            qslookup = self.data.get('lookup', self.unique_id)
            with transaction.atomic():
                for i, d in enumerate(self.data['data']):
                    if qslookup in d["data"]:
                        qs = self.__class__.objects.filter(
                                         **{qslookup:d['data'][qslookup]}
                                                         )
                        self._update_entity(qs, d, to_remove)
                    else:
                        raise KeyError("Lookup {} was not found in object "
                                       "number {}".format(qslookup, i))
    
    def put(self, request, *args, **kwargs):
        '''
        The put currently only accepts json. Json generically looks like:
        
        {  
            "data" : {
                "<data_field_name>" : "<data>" | <data>, ...
            },
            "<m2m>" : {
                "add" : [ .... ],
                "delete" : [ .... ]
            }
        }
        
        Note that you can update from a queryset relative to the rules of a get. 
        Meaning you can search for a set of entities to update at once.
        
        Filtering is done in the same way as GET.
        
        To perform a multi update, pass in an array for data and all query
        params from the url query will be ignored in favor of the data provided
        in the individual objects. You can only update on the given entity, 
        and you must provide the lookup value to help determine what entity
        or entities need to be updated with the given data.
        
        The json object should then look as follows:
        
        {
            "lookup" : "<field_lookup>",
            "data" : [
                {
                    "data" : {
                        "<data_field_name>" : "<data>" | <data>, ...
                    },
                    "<m2m>" : {
                        "add" : [ .... ],
                        "delete" : [ .... ]
                    }
                }
            ]
        }
        
        Be careful, it does not validate that this is a unique lookup and will
        update all values returned in the qs. If you do not provide a lookup, it
        will assume the pk and will search for the pk in the body of the data.
        If the pk is not found, then an error is thrown and none are updated.
        '''
        try:
            self.do_put(request, *args, **kwargs)
        except (KeyError, FieldDoesNotExist, TypeError) as e:
            return err(e)
        return other_response()
    
    def delete(self, request, *args, **kwargs):
        '''
        Delete an entity. This is a no payload endpoint where you can delete 
        either in bulk or singly.
        
        Filtering is done in the same way as GET.
        
        Will return status 204 if successful.
        '''
        args = self._get_ids_from_args(*args)
        if not args:
            if "ids" not in self.params:
                return err("Did not contain any valid ids to delete.")
        try:
            deletes = self._get_qs(*args, **kwargs)   
        except TypeError as e:
            return err(e)
        deletes.delete()
        return other_response()
    
    def head(self, request, *args, **kwargs):
        '''
        Return just the headers of a call.
        '''
        return HttpResponse()
    
    def options(self, request, *args, **kwargs):
        '''
        Return the options available for the endpoint. Add the _no_display field
        to a mview to prevent it from being displayed but still retrieved. Add
        the _no_update_fields to a mview to prevent the ui from attempting to
        update (and to prevent the server from updating).
        
        To customize display order for a class, add the _display_order
        attribute and it will maintain the order that the object fields should
        be displayed if used in a table.
        '''
        updates = getattr(self.__class__, '_no_update_fields', [])
        data = {
                "resource" : self.__class__.__name__,
                "description" : self.__doc__,
                "content_types": self.return_types,
                "accepts" : self.parses,
                "no_updates" : [] if updates is None else updates + ['id'],
                "no_display" : getattr(self.__class__, '_no_display', []),
                "display_order" : getattr(self.__class__, '_display_order', []),
                "fields" : list(self.field_names),
                "req_perms" : getattr(self, '_perms', {}),
                "perm_level" : getattr(request.user, 'rev_levels', {})
                }
        return other_response(dumps(data), 
                              {'allow' : ','.join(self.allowed_methods)})
        
class ModelAsView(ModelWrapper, BaseModelAsView):

    class Meta:
        abstract = True

class UserManager(BaseUserManager):
    def create_user(self, email, password=None):
        """
        Creates and saves a Poster with the given email and password.
        """
        if not email:
            raise ValueError('Users must have an email address')

        user = self.model(email=self.normalize_email(email))
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, date_of_birth, password):
        """
        Creates and saves a superuser with the given email and password.
        """
        user = self.create_user(email, password=password)
        user.level = 5
        user.save(using=self._db)
        return user

class UserModelAsView(ABUWrapper, BaseModelAsView):
    """
    Defines a few base attributes of the user. These can changed by subclassing
    ABUWrapper instead of using this class.
    """
    email = m.EmailField('The email of the user. This is also the '
                                'username.', 
                         max_length = 254, 
                         unique=True
                         )
    objects = UserManager()    
    
    class Meta:
        abstract = True