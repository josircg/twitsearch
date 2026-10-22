from django.urls import path

from utils.deploy import system_update, system_update_git

urlpatterns = [
    path('system_update/', system_update, name='system_update'),
    path('system_update_git/', system_update_git, name='system_update_git'),
]
