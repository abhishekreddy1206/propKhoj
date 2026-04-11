from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0012_property_embedding_content_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversation',
            name='summary',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='conversation',
            name='summary_message_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='property',
            name='embedding_text',
            field=models.TextField(blank=True, null=True),
        ),
    ]
