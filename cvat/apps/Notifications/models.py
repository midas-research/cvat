from django.db.models import *

from django.contrib.auth.models import User
# Create your models here.

class Notifications(Model):
    title = CharField(max_length=255)
    message = TextField()
    extra_data = JSONField(blank=True, null=True)
    created_at = DateTimeField(auto_now_add=True)
    is_read = BooleanField(default=False)
    read_at = DateTimeField(blank=True, null=True)

    recipient = ManyToManyField(User, related_name='notifications')

    notification_type = CharField(max_length=50, choices=[
        ('info', 'Info'),
        ('warning', 'Warning'),
        ('success', 'Success'),
        ('error', 'Error')
    ])

    def __str__(self):
        return f"Notification - {self.title}"