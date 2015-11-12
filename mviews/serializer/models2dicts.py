'''
Created on Nov 11, 2015

@author: derigible

This module takes a set of model objects and converts them into dictionaries.
Unlike the Django serializer, this allows you to expand the serialization and
put in extra data, creating a structured serialization. For example, an object
that contains a Foreign Key object will have that object nested under the name
of the foreign key field:

    {
        ... (object fields),
        "foreign_key_obj" : {
            ... (foreign key object's fields)
        }
    }
    
It also converts fields like FileFields into their useful attributes that could
be used for serialization (such as the url). It will also add the URL for the
entity being serialized if the HYPERLINK_VALUES setting is TRUE in the settings
of your app.
'''

from django.conf import settings
from django.core.files.base import File
from django.db import models
from django.db.models.manager import Manager

from .utils import hyperlinkerize


def convert_to_dicts(qs, field_names, base_type=None, depth=0, rootcall=''):
    """
    Convert a list-like set of model objects into a list of dictionaries. Will
    expand the nested objects in the models to the level determined by the
    depth attribute. The conversion to dictionaries will only consider the
    values in the field_names parameter. 
    
    If the field_names is a list, will only filter the base level objects; 
    other wise, if a dictionary, it should have each foreign key object field 
    name be the key to the list of fields to convert for that object. In this 
    way the select_related calls will be honored without making additional 
    calls to the database (assuming the nested select_related calls are made). 
    For example:
    
        obj1.obj2 = <obj with fields in it>
        
        to filter obj2 pass in a dict as follows:
        
        {
            "base" : [<list of fields to filter on the base level>],
            "obj2" : [<list of fields to filter on the nested obj>]
        }
        
        If any object filter is not included (including the base keyword), then
        it is assumed that all the fields are desired. If using the
        model_as_view, will use the field_names attribute.
        
    If the HYPERLINK_VALUES setting is set as true, then the rootcall needs to
    reflect the non-path part of the URL (ie. "http://example.com"). If left
    empty then a relative path will be provided. It also makes the assumption
    that you are using the model_as_view models, which will in turn provide
    the necessary information to create a hyperlink.
    
    @param qs: a list-like object of models to convert
    @param field_names: if a list, will filter the first-level objects' fields;
                        if a dict, will filter each level by the list provided
                        for that field name
    @param base_type: the base type to check and ensure is not repeated in the
                        return data when depth is greater than 0. If omitted
                        then the check is turned off.
    @param depth: an integer that details how many levels of nested objects to
                    serialize. Defaults to 0.
    @param rootcall: the network location for the hyperlinks.
    """
    vals = []
    if isinstance(field_names, dict):
        filt = field_names.get("base", _get_model_fields(base_type))
    else:
        filt = field_names
    for m in qs:
        obj = {}
        vals.append(obj)
        for f in filt:    
            try:
                field = getattr(m, f)
            except AttributeError:
                continue #not a field on the model
            if isinstance(field, Manager):
                obj[f] = _foreign_rel_to_dict(base_type, 
                                              field, 
                                              1, 
                                              rootcall, 
                                              depth
                                              ) 
            elif isinstance(field, models.Model):
                obj[f] = _foreign_obj_to_dict(base_type, 
                                              field, 
                                              1, 
                                              field_names,
                                              f,
                                              rootcall, 
                                              depth
                                              ) 
            elif isinstance(field, File):
                obj[f] = field.name               
            else:
                obj[f] = field
    return vals

def _get_model_fields(model):
    """
    Gets the model's fields.
    """
    return getattr(model, 'field_names', model._meta.get_all_field_names())

def _get_filter(filters, field, model):
    """
    Get the filter or the field definition for the parsing to occur.
    """
    return filters.get(field, _get_model_fields(model))

def _foreign_obj_to_dict(base_type, 
                         fobj, 
                         depth, 
                         field_filter,
                         field,
                         rootcall, 
                         max_depth=0, 
                         rels=set(), 
                         fos=set()
                        ):
    """
    Basically the same as convert_to_dicts except it keeps track of where the
    conversion has been and how much more it needs to do. It does so by
    keeping track of what foreign_objects have been visited and what relations
    have been visited. If they are seen again they will not be included in the
    output.
    
    It also will pass in the name of the field being used along with the
    field_filter dict to see if there are any fields to be filtered on nested
    objects.
    """
    fields = _get_filter(field_filter, field, fobj)
    fkDict = {}
    for f in fields:
        try:
            fo = getattr(fobj, f)
        except AttributeError:
            fo = getattr(fobj, f+'_set')
        if isinstance(fo, Manager):
            if max_depth >= depth and type(fo) not in rels:
                fkDict[f] = _foreign_rel_to_dict(base_type, 
                                                fo, 
                                                depth + 1,
                                                field_filter,
                                                f,
                                                rootcall,
                                                max_depth,
                                                rels)
        elif isinstance(fo, models.Model):
            if (max_depth >= depth and type(fo) != type(base_type) 
                and type(fo) not in fos):
                fos.add(type(fobj))
                fkDict[f] = _foreign_obj_to_dict(base_type, 
                                                fo, 
                                                depth + 1, 
                                                field_filter,
                                                f,
                                                rootcall,
                                                max_depth,
                                                rels,
                                                fos)
                fos.remove(type(fobj))
        elif isinstance(fo, File):
            fkDict[f] = fo.name  
        else: 
            fkDict[f] = fobj.serializable_value(f)
    if getattr(settings, 'HYPERLINK_VALUES', True):
        fkDict["url"] = hyperlinkerize(fkDict[getattr(fobj, 'unique_id', 'id')], 
                                      rootcall, 
                                      fobj) 
    
    return fkDict

def _foreign_rel_to_dict(base_type, 
                         frel, 
                         depth,
                         field_filter,
                         field, 
                         rootcall, 
                         max_depth=0, 
                         rels=set()
                         ):
    """
    Expands all of the objects in a relation field. This could be a many-to-many, 
    or a many-to-one relationship.
    """
    rels.add(type(frel))
    fks = []
    for fk in frel.all():
        if max_depth >= depth:
            fkDict = _foreign_obj_to_dict(base_type, 
                                          fk, 
                                          depth + 1, 
                                          field_filter,
                                          field,
                                          rootcall, 
                                          max_depth, 
                                          rels)
            fks.append(fkDict)
    return fks
