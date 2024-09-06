from rest_framework import serializers

from .models import *


class NotificationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notifications
        fields = ['id', 'title', 'message', 'notification_type', 'extra_data', 'created_at', 'is_read', 'read_at']
        read_only_fields = ['id', 'created_at', 'is_read', 'read_at']