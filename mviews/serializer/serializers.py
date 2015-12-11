'''
Created on Nov 11, 2015

@author: derigible

Methods that will do the actual serialization of data.
'''

import json

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder as djson

from .models2dicts import convert_to_dicts as c2d
from .utils import create_paging_dict
from .utils import hyperlinkerize

def _serialize_json(qs, 
                    fields, 
                    unique_id='id', 
                    depth=0, 
                    paginate=0, 
                    page=1, 
                    rootcall='', 
                    url_path='', 
                    extra = None
                    ):
    """
    Serialize a queryset into json. If expand is true, will treat the qs as 
    models; if false, will treat as dictionaries. If the settings has included
    the RETURN_SINGLES=TRUE attribute, will return 1-length querysets as a 
    single object without meta-data attached (also the default behavior).
    
    Any extra values retrieved before serialization but not apart of the 
    mview can be passed with the extra param. This needs to be json serializable
    data.
    """
    return_single = (len(qs) > 1 
                     or paginate 
                     or not getattr(settings, "RETURN_SINGLES", True)
                     )
    
    if paginate:
        qs, rslt = create_paging_dict(qs, 
                                      url_path, 
                                      paginate, 
                                      page, 
                                      rootcall
                                      )
        rslt["data"] = []
    else:
        rslt = {"count" : len(qs), "data" : []}
    if not depth:  
        if return_single:
            rslt["data"] = list(qs)
        else:
            rslt = list(qs)[0] if len(qs) > 0 else rslt
    else:  
        vals = c2d(qs, fields, depth, rootcall)
        if return_single:
            rslt["data"] = vals
        else:
            rslt = vals.pop() if len(vals) else rslt
    if getattr(settings, 'HYPERLINK_VALUES', True) and not fields:
        if return_single:
            for r in rslt["data"]:
                r["url"] = hyperlinkerize(r[unique_id], 
                                          rootcall, 
                                          url_path) 
        elif len(qs) != 0:
            rslt["url"] = hyperlinkerize(rslt[unique_id], 
                                          rootcall, 
                                          url_path) 
    if extra is not None:
        rslt['extra'] = extra
    return json.dumps(rslt, cls=djson)

def _serialize_xml(mview, qs, expand):
    """
    Serialize a queryset into xml.
    """
    raise NotImplementedError("Parsing of query sets to xml not yet supported.")