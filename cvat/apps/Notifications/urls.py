from django.urls import path, include
from rest_framework import routers

from .views import *

router = routers.DefaultRouter(trailing_slash=False)
router.register('notifications', NotificationsViewSet,  basename='notifications')

urlpatterns = router.urls
