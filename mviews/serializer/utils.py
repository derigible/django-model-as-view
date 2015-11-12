'''
Created on Nov 11, 2015

@author: derigible

Utility functions to be used in the seriliazation framework. These generally
are not useful except within this framework.
'''

import math

from django.conf import settings


def hyperlink(rootcall, path, append = ''):
    """
    Produce a hyperlink for the call. Only produces a hyperlink if rootcall is
    not empty. If you don't want to hyperlink values, set the
    project setting HYPERLINK_VALUES = False.
    
    @param rootcall: the rootcall of the request
    @param path: the path to the entity
    @param append: append a string (ie query) to the hyperlink
    @return the hyperlink to the base model
    """
    if rootcall and getattr(settings, 'HYPERLINK_VALUES', True):
        return "{}/{}/{}".format(rootcall, path, append)
    return append

def hyperlinkerize(value, rootcall, mview):
    """
    Make the resource a hyperlink to the field. Only makes it as a hyperlink
    if rootcall is not empty. If you don't want to hyperlink values, set the
    project setting HYPERLINK_VALUES = False.
    
    @param value: the field value
    @param rootcall: the http(s)://domain
    @param mview: the model the field rests in
    @return the data to send back, either hyperlinked or not
    """
    if rootcall and getattr(settings, 'HYPERLINK_VALUES', True):
        return hyperlink(rootcall, mview.url_path, '{}/'.format(value))
    else:
        return value
    
def paginator(queryset, limit=10, page_num=1):
    '''
    Figures out the pagination for the queryset provided. This queryset should
    be a select statement only that does not do any sort of counting or 
    limiting to the call. I didn't like the way Django does pagination, 
    so I wrote my own.
    
    @param request: the request of the call
    @param queryset: the queryset to paginate
    @param limit: the limit of the entities in the page
    @return the sliced queryset by page
    @return a dictionary of values: {count: the number of entities, 
                number_pages: number of pages, 
                page_num: the page number, 
                limit: number of entities for page}
    '''
    try:
        to_return = limit = 10 if int(limit) <= 0 else int(limit)
    except TypeError:
        to_return = limit = 10
    try:
        page_num = int(page_num)
    except TypeError:
        page_num = 1
    count = queryset.count()
    number_pages = max(math.floor(count/ limit), 2 if count > limit else 1)
    page_num = page_num if page_num <= number_pages else number_pages
    offset = limit * (page_num-1) #get the start of the page
    #get the rest of the runs for the last page
    if page_num == number_pages and count - offset > 0 and page_num > 1:
        to_return = count - offset
    end = to_return * page_num
    return queryset[offset:end], {"count" : count, 
                                  "number_of_pages" : number_pages, 
                                  "page_num" : page_num, 
                                  "limit" : limit,
                                  "returned" : to_return}
    
def create_paging_dict(qs, path="/", limit=1, page=1, rootcall):
    """
    Create the paging dictionary used for returns to the client. It will also
    output the paginated queryset. You can also pass in a path that will make
    a hyperlink if the HYPERLINK_VALUES is set to true. If not passed in, will
    create a URL with no path.
    
    @param qs: the queryset to paginate
    @param path: the path to the view for the hyperlink to the next page
    @param limit: the limit of the items to return (default 10)
    @param page: the page of the items to return (default 1)
    @param rootcall: the protocol-domain combo as string
    @return the new queryset and the paging dict
    """
    qs, paging = paginator(qs, limit, page)  
    page_count = paging.get("number_of_pages", 1)
    page_number = paging.get("page_num", 1)
    total_entities = paging.get("count", len(qs))
    number_per_page = paging.get("limit", len(qs))
    returned = paging.get("returned", len(qs))
    rslt = {
           "count" : len(qs),
           "page_count" : page_count,
           "last_page" : hyperlink(rootcall, 
                               path, 
                               '?_page={}{}'.format(page_count,
                                                    '&_limit={}'
                                                    .format(number_per_page)
                                                    )
                                   ),
           "page_number" : page_number,
           "total_entities" : total_entities,
           "number_per_page" : number_per_page,
           "number_returned" : returned,
           "next" : (
                     hyperlink(rootcall, 
                               path, 
                               '?_page={}{}'.format(page_number + 1,
                                                    '&_limit={}'
                                                    .format(number_per_page)
                                                    )
                               )
                     if page_number + 1 <= page_count else None
                     ),
           "previous" : (
                         hyperlink(rootcall, 
                                   path, 
                                   '?_page={}{}'.format(page_number - 1,
                                                    '&_limit={}'
                                                    .format(number_per_page)
                                                        )
                                                    
                                   ) 
                     if page_number - 1 <= page_count and
                        page_number - 1 > 0 else None
                        )
            }
    return qs, rslt