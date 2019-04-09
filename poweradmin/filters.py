# coding: utf-8
from django.contrib.admin.filters import RelatedFieldListFilter, AllValuesFieldListFilter, FieldListFilter
from django.contrib.admin.utils import reverse_field_path


class CustomQuerysetAllValuesFieldListFilter(AllValuesFieldListFilter):
    # Usado apenas para filtros por campos.
    def __init__(self, field, request, params, model, model_admin, field_path):
        super(CustomQuerysetAllValuesFieldListFilter, self).__init__(
            field, request, params, model, model_admin, field_path)

        parent_model, reverse_path = reverse_field_path(model, self.field_path)

        queryset = parent_model._default_manager.all()
        qs_dict = getattr(model_admin, 'queryset_filter', None)

        if qs_dict and field_path in qs_dict:
            queryset = qs_dict[field_path]

        if isinstance(queryset, str):
            # Define title
            if hasattr(getattr(model_admin, queryset), 'short_description'):
                self.title = getattr(getattr(model_admin, queryset), 'short_description')
            queryset = getattr(model_admin, queryset)(request)

        self.lookup_choices = queryset.distinct().order_by(field.name).values_list(field.name, flat=True)


class CustomRelatedFieldListFilter(RelatedFieldListFilter):
    '''
        Usado apenas para filtros por FK.
    '''
    def __init__(self, field, request, params, model, model_admin, field_path):
        super(CustomRelatedFieldListFilter, self).__init__(field, request, params, model, model_admin, field_path)

        queryset_filter = getattr(model_admin, 'queryset_filter', None)
        if queryset_filter and field_path in queryset_filter:
            queryset = getattr(model_admin, queryset_filter[field_path])(request)
            lookup_choices = []
            for query in queryset:
                lookup_choices.append((query.pk, u'%s' % query))
            self.lookup_choices = lookup_choices

new_filter_list = []
for test, _filter in FieldListFilter._field_list_filters:
    if issubclass(_filter, AllValuesFieldListFilter):
        new_filter_list += [(test, CustomQuerysetAllValuesFieldListFilter)]
        continue
    if issubclass(_filter, RelatedFieldListFilter):
        new_filter_list += [(test, CustomRelatedFieldListFilter)]
        continue

    new_filter_list += [(test, _filter)]

FieldListFilter._field_list_filters = new_filter_list