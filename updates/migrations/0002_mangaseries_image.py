# Generated by Django 2.1.5 on 2021-04-19 13:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('updates', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='mangaseries',
            name='image',
            field=models.ImageField(default='default.jpg', upload_to='manga_images/'),
        ),
    ]
