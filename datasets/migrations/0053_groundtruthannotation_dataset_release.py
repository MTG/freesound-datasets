# Generated by Django 2.0.8 on 2018-10-22 16:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0052_auto_20180831_1652'),
    ]

    operations = [
        migrations.AddField(
            model_name='groundtruthannotation',
            name='dataset_release',
            field=models.ManyToManyField(related_name='ground_truth_annotations', to='datasets.DatasetRelease'),
        ),
    ]
