"""
A package that is committed to taking the best of the Django ORM and fixing
the poor serialization efforts

It also attempts to intelligently determine what serialization to use depending
on the Accept header passed in to the service. If no Accept header is
found, or the type is not supported, will default to application/json.

To make this possible, a few more attributes must be added to a model:

    1) the base queryset for the model must be added as the qs attribute
"""

from django.http.response import HttpResponse as resp

from .serializers import _serialize_json


def serialize(mview, qs, serializer=None, rootcall='', extra = None):
    """
    One of two public methods of this package. Pass in the ModelAsView object 
    and the qs you wish to serialize with the model it is querying
    and the return value will be either json or xml. Other values are not 
    currently supported, but a serializer that accepts a query set  
    as argument may be used by passing it in through the serializer keyword.
    
    It is assumed that the models have added the proper attributes to fit in
    with this packages idea of what a model should look like.
    
    @param mview: the mview object
    @param qs: the queryset being parsed
    @param serializer: the serializer to use
    @param rootcall: the root of the call to use in hyperlinked returns
    @param extra: any extra data to serialize that is not apart of the mview
    @return the serialized string of queryset qs
    """
    if serializer is not None:
        return serializer(qs)
#     if "xml" in mview.accept:
#         return _serialize_xml(qs, rootcall)
    if mview.fields:
        #get all of the field names specified and in the model
        field_names = set(mview.fields).intersection(mview.field_names)
    else:
        field_names = set(mview.field_names)  
    return _serialize_json(qs,
                           field_names, 
                           unique_id=mview.unique_id,
                           depth=mview.sdepth,
                           paginate=mview.params.get('_limit', 
                                                     getattr(mview, 
                                                             '__paginate',
                                                              0)
                                                     ),
                           page=mview.params.get('_page', 1),
                           rootcall=rootcall, 
                           url_path=mview.url_path,
                           extra=extra)
    
def serialize_to_response(mview, qs, serializer=None, rootcall='', extra = None):
    """
    One of two public methods of this package. Pass in the ModelAsView object
    and the qs you wish to serialize and the return value will be either json
    or xml. Other values are not currently supported, but a serializer that
    accepts a model as a single argument may be used by passing it in
    through the serializer keyword.
    
    The Accept header is used to set the content_type of the response and
    a django.http.response.HttpResponse object is returned. If you pass in
    a custom serializer, you must set the response's content_type to the
    correct content_type manually.
    
    It is assumed that the models have added the proper attributes to fit in
    with this packages idea of what a model should look like.
    
    @param mview: the mview object
    @param qs: the queryset being parsed
    @param serializer: the serializer to use
    @param rootcall: the root of the call to use in hyperlinked returns
    @param extra: any extra data to serialize that is not apart of the mview
    @return a response object with the serialized data as payload
    """
    retData = serialize(mview, qs, serializer, rootcall, extra)
    if "xml" in mview.accept:
        ct = "application/xml"
    else:
        ct = "application/json"
    return resp(retData, content_type=ct)