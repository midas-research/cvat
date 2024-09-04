from django.urls import path, include

from .views import *


urlpatterns = [
    path('api/notifications/', NotificationsViewSet.as_view({'post': 'SendNotification'}), name='send-notification'),
    path('api/notifications/fetch/', NotificationsViewSet.as_view({'get': 'FetchUserNotifications'}), name='fetch-notifications'),
    path('api/notifications/mark-viewed/', NotificationsViewSet.as_view({'post': 'MarkNotificationAsViewed'}), name='mark-notification-viewed'),
]