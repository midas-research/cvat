# Generated by Django 4.2.6 on 2024-04-05 04:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("engine", "0080_remove_labeledimage_locale_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="labeledimage",
            name="audio_locale",
            field=models.TextField(default="en"),
        ),
        migrations.AddField(
            model_name="labeledshape",
            name="audio_locale",
            field=models.TextField(default="en"),
        ),
        migrations.AddField(
            model_name="labeledtrack",
            name="audio_locale",
            field=models.TextField(default="en"),
        ),
        migrations.AddField(
            model_name="trackedshape",
            name="audio_locale",
            field=models.TextField(default=""),
        ),
    ]