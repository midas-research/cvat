from django.shortcuts import render
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.response import Response

import traceback

from .models import *
# Create your views here.

## Usage
# from rest_framework.test import APIRequestFactory

# request_data = {
#     "user": 1,
#     "title": "Test Notification",
#     "message": "This is a test notification message.",
#     "notification_type": "info",
#     "extra_data": {"key": "value"}
# }
# factory = APIRequestFactory()
# req = factory.post('/api/notifications', request_data, format='json')
# notifications_view = NotificationsViewSet.as_view({'post': 'SendNotification'})
# response = notifications_view(req)
class NotificationsViewSet(viewsets.ViewSet):
    isAuthorized = True


    def AddNotification(self, req):
        try:
            notification = Notifications.objects.create(
                title = req.get('title'),
                message = req.get('message'),
                notification_type = req.get('notification_type'),
                extra_data = req.get('extra_data', {}),
            )
            notification.save()

            return Response(
                {
                    "success" : True,
                    "message" : "An error occurred while saving notification.",
                    "data" : {
                        "notification" : notification
                    },
                    "error" : error
                }
            )
        except Exception as e:
            error = traceback.format_exc()

            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while saving notification.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def SendNotification(self, request):
        try:
            req = request.data

            if "user" in req or "org" in req:
                response = self.AAddNotification(req)

                if not response["success"]:
                    return response

                notification = response["data"]["notification"]

                if "user" in req:
                    user = req["user"]
                    response = self.SendUserNotifications(notification, user, req)
                elif "org" in req:
                    response = self.SendOrganizationNotifications(notification, req)
            else:
                return Response(
                    {
                        "success" : False,
                        "message" : "Invalid request data. 'user' or 'org' key is required.",
                        "data" : {},
                        "error" : None
                    },
                    status = status.HTTP_400_BAD_REQUEST
                )

            if response["success"] == False:
                self.try_delete_notification(notification)

            return response
        except Exception as e:
            error = traceback.format_exc()

            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while sending notification.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def SendUserNotifications(self, notification, usr, req):
        try:
            user = User.objects.get(id=usr)
            notification.recipient.add(user)

            return Response(
                {
                    "success" : True,
                    "message" : "Notification sent successfully.",
                    "data" : {},
                    "error" : None
                },
                status = status.HTTP_201_CREATED
            )
        except User.DoesNotExist:
            return Response(
                {
                    "success" : False,
                    "message" : f"User with id {usr} does not exist.",
                    "data" : {},
                    "error" : None
                },
                status = status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            error = traceback.format_exc()

            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while sending user notification.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def SendOrganizationNotifications(self, notification, req):
        try:
            organization = Organization.objects.get(id=req["org"])
            members = organization.members.filter(is_active=True)
            errors = []

            for member in members:
                user = member.user
                response = self.SendUserNotifications(user.id, req)

                if not response.data.get("success"):
                    errors.append(f"Error occurred while sending notification to user ({user.username}). Error: {response.data.get('error')}")

            if not errors:
                return Response(
                    {
                        "success" : True,
                        "message" : "Notifications sent successfully.",
                        "data" : {},
                        "error" : None
                    },
                    status = status.HTTP_200_OK
                )
            else:
                return Response(
                    {
                        "success" : False,
                        "message" : "Unable to send notifications to one or more users.",
                        "data" : {},
                        "error" : errors
                    },
                    status = status.HTTP_504_GATEWAY_TIMEOUT
                )
        except Organization.DoesNotExist:
            return Response(
                {
                    "success" : False,
                    "message" : f"Organization with id {req['org']} does not exist.",
                    "data" : {},
                    "error" : None
                },
                status = status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            error = traceback.format_exc()

            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while sending organization notifications.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def FetchUserNotifications(self, request):
        try:
            user = request.user
            notifications = Notifications.objects.filter(recipient=user)
            data = []

            for notification in notifications:
                noti = {
                    "title" : notification.title,
                    "message" : notification.message,
                    "url" : notification.url,
                    "created_at" : notification.created_at,
                    "is_read" : notification.is_read,
                    "notification_type" : notification.notification_type,
                    "files" : notification.files.url if notification.files else None,
                }
                data.append(noti)

            return Response(
                {
                    "success" : True,
                    "message" : "User notifications fetched successfully.",
                    "data" : {
                        "notifications" : data
                    },
                    "error" : None
                },
                status = status.HTTP_200_OK
            )
        except Exception as e:
            error = traceback.format_exc()

            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while fetching notifications.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def MarkNotificationAsViewed(self, request):
        try:
            notification_id = request.data.get('notification_id')
            notification = Notifications.objects.get(id=notification_id, recipient=request.user)
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()

            return Response(
                {
                    "success" : True,
                    "message" : "Notification marked as viewed.",
                    "data" : {},
                    "error" : None
                },
                status = status.HTTP_200_OK
            )
        except Notifications.DoesNotExist:
            return Response(
                {
                    "success" : False,
                    "message" : f"Notification with id {notification_id} does not exist or does not belong to you.",
                    "data" : {},
                    "error" : None
                },
                status = status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            error = traceback.format_exc()
            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while marking notification as viewed.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )
