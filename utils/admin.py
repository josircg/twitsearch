from django.contrib import admin, messages
from django.contrib.admin.models import LogEntry, CHANGE
from poweradmin.admin import PowerModelAdmin, PowerButton


@admin.register(LogEntry)
class LogEntryAdmin(PowerModelAdmin):
    list_filter = ('action_time', 'content_type', 'action_flag',)
    list_display = ('action_time', 'user', 'content_type', 'tipo', 'object_repr', 'change_message', )
    fields = ('action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'tipo',
              'change_message', )
    readonly_fields = ('action_time', 'user', 'content_type', 'object_id', 'object_repr', 'action_flag', 'tipo',
                       'change_message', )
    multi_search = (
        ('q1', u'Repr. do Objeto', ['object_repr', ]),
        ('q2', u'Mensagem', ['change_message', ]),
        ('q3', u'User', ['user__username', ]),
    )

    def tipo(self, obj):
        if obj.is_addition():
            return u"1-Adicionado"
        elif obj.is_change():
            return u"2-Modificado"
        elif obj.is_deletion():
            return u"3-Deletado"

