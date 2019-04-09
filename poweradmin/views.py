# -*- coding: utf-8 -*-
from django.contrib.admin.options import IncorrectLookupParameters
from django.core.exceptions import SuspiciousOperation, ImproperlyConfigured
from django.core.paginator import InvalidPage
from django.db import models
from django.utils.encoding import force_text
from django.utils.encoding import smart_str
from django.utils.translation import ugettext, ugettext_lazy
from django.utils.http import urlencode
import operator

from django.contrib.admin.views.main import ChangeList, SEARCH_VAR
from django.contrib.admin.utils import (quote, get_fields_from_path,
    lookup_needs_distinct, prepare_lookup_value)

from functools import reduce

class PowerChangeList(ChangeList):

    def __init__(self, request, model, list_display, list_display_links,
            list_filter, date_hierarchy, search_fields, list_select_related,
            list_per_page, list_max_show_all, list_editable, model_admin):
        #Criando o multi_search_query
        self.multi_search_query = {}
        request.GET._mutable = True
        for k, l, f in model_admin.multi_search:
            if k in request.GET:
                self.multi_search_query[k] = request.GET.get(k, '')
                del request.GET[k]
        request.GET._mutable = False
        super(PowerChangeList, self).__init__(request, model, list_display, list_display_links,
            list_filter, date_hierarchy, search_fields, list_select_related,
            list_per_page, list_max_show_all, list_editable, model_admin)

    def get_results(self, request):
        paginator = self.model_admin.get_paginator(request, self.queryset, self.list_per_page)
        # Get the number of objects, with admin filters applied.
        result_count = paginator.count

        # Get the total number of objects, with no admin filters applied.
        # Perform a slight optimization:
        # full_result_count is equal to paginator.count if no filters
        # were applied
        if self.get_filters_params() or self.params.get(SEARCH_VAR) or self.multi_search_query:
            full_result_count = self.root_queryset.count()
        else:
            full_result_count = result_count
        can_show_all = result_count <= self.list_max_show_all
        multi_page = result_count > self.list_per_page

        # Get the list of objects to display on this page.
        if (self.show_all and can_show_all) or not multi_page:
            result_list = self.queryset._clone()
        else:
            try:
                result_list = paginator.page(self.page_num + 1).object_list
            except InvalidPage:
                raise IncorrectLookupParameters

        self.result_count = result_count
        self.full_result_count = full_result_count
        self.result_list = result_list
        self.can_show_all = can_show_all
        self.multi_page = multi_page
        self.paginator = paginator

    def get_queryset(self, request):
        MULTI_SEARCH_VAR = []
        for var, label, query in self.model_admin.multi_search:
            MULTI_SEARCH_VAR.append(var)

        # First, we collect all the declared list filters.
        (self.filter_specs, self.has_filters, remaining_lookup_params,
         filters_use_distinct) = self.get_filters(request)

        # Then, we let every list filter modify the queryset to its liking.
        qs = self.root_queryset
        for filter_spec in self.filter_specs:
            new_qs = filter_spec.queryset(request, qs)
            if new_qs is not None:
                qs = new_qs

        try:
            # Finally, we apply the remaining lookup parameters from the query
            # string (i.e. those that haven't already been processed by the
            # filters).
            qs = qs.filter(**remaining_lookup_params)
        except (SuspiciousOperation, ImproperlyConfigured):
            # Allow certain types of errors to be re-raised as-is so that the
            # caller can treat them in a special way.
            raise
        except Exception as e:
            # Every other error is caught with a naked except, because we don't
            # have any other way of validating lookup parameters. They might be
            # invalid if the keyword arguments are incorrect, or if the values
            # are not in the correct type, so we might get FieldError,
            # ValueError, ValidationError, or ?.
            raise IncorrectLookupParameters(e)

        if not qs.query.select_related:
            qs = self.apply_select_related(qs)

        # Set ordering.
        ordering = self.get_ordering(request, qs)
        qs = qs.order_by(*ordering)

        # Apply keyword searches.
        def construct_search(field_name):
            if field_name.startswith('^'):
                return "%s__istartswith" % field_name[1:]
            elif field_name.startswith('='):
                return "%s__iexact" % field_name[1:]
            elif field_name.startswith('@'):
                return "%s__search" % field_name[1:]
            else:
                return "%s__icontains" % field_name

        use_distinct = False
        #Faz o filter do multi_search
        if self.multi_search_query:
            for k_query, query in self.multi_search_query.items():
                for k, l, f in self.model_admin.multi_search:
                    if k_query == k:
                        fields = f
                        break
                if fields and query:
                    orm_lookups = [construct_search(str(field))
                                   for field in fields]
                    for bit in query.split():
                        or_queries = [models.Q(**{orm_lookup: bit}) for orm_lookup in orm_lookups]
                        qs = qs.filter(reduce(operator.or_, or_queries))
                    if not use_distinct:
                        for search_spec in orm_lookups:
                            if lookup_needs_distinct(self.lookup_opts, search_spec):
                                use_distinct = True
                                break

        elif self.search_fields and self.query:
            orm_lookups = [construct_search(str(search_field))
                           for search_field in self.search_fields]
            for bit in self.query.split():
                or_queries = [models.Q(**{orm_lookup: bit})
                              for orm_lookup in orm_lookups]
                qs = qs.filter(reduce(operator.or_, or_queries))
            if not use_distinct:
                for search_spec in orm_lookups:
                    if lookup_needs_distinct(self.lookup_opts, search_spec):
                        use_distinct = True
                        break

        if filters_use_distinct | use_distinct:
            return qs.distinct()
        else:
            return qs