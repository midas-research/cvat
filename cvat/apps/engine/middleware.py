# Copyright (C) 2023 CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from uuid import uuid4
from .models import Subscriber, Project, Task, Job
from django.core.exceptions import PermissionDenied
from rest_framework.views import APIView


class RequestTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    @staticmethod
    def _generate_id():
        return str(uuid4())

    def __call__(self, request):
        request.uuid = self._generate_id()
        response = self.get_response(request)
        response.headers["X-Request-Id"] = request.uuid

        return response


class ProjectLimitCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            project_creation_path = "/api/projects"
            drf_request = APIView().initialize_request(request)
            user = drf_request.user

            if request.path == project_creation_path:
                project_count = Project.objects.filter(owner=user).count()

                try:
                    subscription = Subscriber.objects.get(user=user)

                    if (
                        subscription.subscription_class == "basic"
                        and project_count >= 3
                    ):
                        raise PermissionDenied(
                            "You have reached your limit of 3 projects. Please subscribe for more."
                        )
                    elif (
                        subscription.subscription_class == "silver"
                        and project_count >= 5
                    ):
                        raise PermissionDenied(
                            "You have reached your limit of 5 projects. Please upgrade to Gold for unlimited projects."
                        )
                except Subscriber.DoesNotExist:
                    if project_count >= 3:
                        raise PermissionDenied(
                            "You have reached your limit of 3 projects. Please subscribe for more."
                        )

        response = self.get_response(request)
        return response


class TaskLimitCheckMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST":
            task_creation_path = "/api/tasks"
            drf_request = APIView().initialize_request(request)
            user = drf_request.user

            if request.path == task_creation_path:
                task_count = Task.objects.filter(owner=user).count()

                try:
                    subscription = Subscriber.objects.get(user=user)

                    if subscription.subscription_class == "basic" and task_count >= 10:
                        raise PermissionDenied(
                            "You have reached your limit of 10 tasks. Please subscribe for more."
                        )
                    elif (
                        subscription.subscription_class == "silver" and task_count >= 20
                    ):
                        raise PermissionDenied(
                            "You have reached your limit of 20 tasks. Please upgrade to Gold for unlimited tasks."
                        )
                except Subscriber.DoesNotExist:
                    if task_count >= 10:
                        raise PermissionDenied(
                            "You have reached your limit of 10 tasks. Please subscribe for more."
                        )

        response = self.get_response(request)
        return response


class ExportJobAnnotationsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET":
            drf_request = APIView().initialize_request(request)
            user = drf_request.user

            if (
                request.path.startswith("/api/jobs/")
                and request.path.endswith("/annotations")
                and "format" in request.GET
            ):
                try:

                    subscription = Subscriber.objects.get(user=user)

                    if subscription.subscription_class == "basic":
                        raise PermissionDenied(
                            "Exporting annotations with videos is not available for Basic subscription."
                        )
                    elif subscription.subscription_class in ["silver", "gold"]:

                        pass

                except Job.DoesNotExist:
                    raise PermissionDenied(
                        "Job not found or you do not have permission to access it."
                    )
                except Subscriber.DoesNotExist:
                    raise PermissionDenied(
                        "You need a valid subscription to export annotations with videos."
                    )

        response = self.get_response(request)
        return response


class ExportTaskAnnotationsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "GET":
            drf_request = APIView().initialize_request(request)
            user = drf_request.user

            if (
                request.path.startswith("/api/tasks/")
                and request.path.endswith("/annotations")
                and "format" in request.GET
            ):
                try:

                    subscription = Subscriber.objects.get(user=user)

                    if subscription.subscription_class == "basic":
                        raise PermissionDenied(
                            "Exporting task annotations with audio is not available for Basic subscription."
                        )
                    elif subscription.subscription_class in ["silver", "gold"]:

                        pass

                except Task.DoesNotExist:
                    raise PermissionDenied(
                        "Task not found or you do not have permission to access it."
                    )
                except Subscriber.DoesNotExist:
                    raise PermissionDenied(
                        "You need a valid subscription to export task annotations with audio."
                    )

        response = self.get_response(request)
        return response


class ProjectTaskLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path == "/api/tasks":
            drf_request = APIView().initialize_request(request)
            user = drf_request.user

            project_id = drf_request.data.get("project_id")

            if project_id:
                try:

                    subscription = Subscriber.objects.get(user=user)

                    project = Project.objects.get(id=project_id)

                    task_count = Task.objects.filter(project=project).count()

                    if subscription.subscription_class == "basic" and task_count >= 5:
                        raise PermissionDenied(
                            "Basic subscription allows up to 5 tasks per project. Please upgrade to add more tasks."
                        )
                    elif (
                        subscription.subscription_class == "silver" and task_count >= 10
                    ):
                        raise PermissionDenied(
                            "Silver subscription allows up to 10 tasks per project. Please upgrade to add more tasks."
                        )
                    elif subscription.subscription_class == "gold":

                        pass

                except Project.DoesNotExist:
                    raise PermissionDenied("Project not found.")
                except Subscriber.DoesNotExist:
                    raise PermissionDenied(
                        "You need a valid subscription to create tasks in a project."
                    )

        response = self.get_response(request)
        return response
