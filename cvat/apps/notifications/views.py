from django.shortcuts import render
from django.utils import timezone

from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from .models import *
from .serializers import *

import json
import traceback
# Create your views here.

## Usage
class NotificationsViewSet(viewsets.ViewSet):
    isAuthorized = True


    def AddNotification(self, req):
        try:
            print("Saving Notifications")
            notification = Notifications.objects.create(
                title = req['title'],
                message = req['message'],
                notification_type = req['notification_type']
            )
            notification.save()

            return Response(
                {
                    "success" : True,
                    "message" : "An error occurred while saving notification.",
                    "data" : {
                        "notification" : notification
                    },
                    "error" : None
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


    def SendNotification(self, request: Request):
        try:
            print("Sending...")
            body = request.body.decode('utf-8')
            req = json.loads(body)

            if "user" in req or "org" in req:
                response = self.AddNotification(req)

                if not response.data["success"]:
                    return response

                notification = response.data["data"]["notification"]

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

            if response.data["success"] == False:
                pass
                # self.try_delete_notification(notification)

            return response
        except Exception as e:
            error = traceback.format_exc()
            print(error)

            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while sending notification.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def SendUserNotifications(self, notification, usr):
        try:
            user = User.objects.get(id = usr)
            notification.recipient.add(user)
            notification.save()

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
                response = self.SendUserNotifications(notification, user.id)

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
            print(error)

            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while sending organization notifications.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    def FetchUserNotifications(self, request: Request):
        try:
            user = request.user
            notifications = Notifications.objects.filter(recipient=user)
            data = []

            for notification in notifications:
                noti = {
                    "title" : notification.title,
                    "message" : notification.message,
                    "created_at" : notification.created_at,
                    "is_read" : notification.is_read,
                    "notification_type" : notification.notification_type
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


    def MarkNotificationAsViewed(self, request: Request):
        try:
            notification_ids = request.data.get('notification_ids', [])

            if not isinstance(notification_ids, list):
                raise ValueError("Notification IDs should be provided as a list.")

            notifications = Notifications.objects.filter(id__in=notification_ids, recipient=request.user)
            updated_count = notifications.update(is_read=True, read_at=timezone.now())

            if updated_count == 0:
                return Response(
                    {
                        "success" : False,
                        "message" : "No notifications found or none belong to you.",
                        "data" : {},
                        "error" : None
                    },
                    status=status.HTTP_404_NOT_FOUND
                )

            return Response(
                {
                    "success" : True,
                    "message" : f"{updated_count} notifications marked as viewed.",
                    "data" : {},
                    "error" : None
                },
                status=status.HTTP_200_OK
            )
        except ValueError as ve:
            return Response(
                {
                    "success" : False,
                    "message" : str(ve),
                    "data" : {},
                    "error" : None
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            error = traceback.format_exc()
            return Response(
                {
                    "success" : False,
                    "message" : "An error occurred while marking notifications as viewed.",
                    "data" : {},
                    "error" : error
                },
                status = status.HTTP_500_INTERNAL_SERVER_ERROR
            )