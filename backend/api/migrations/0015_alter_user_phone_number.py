from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0014_upgrade_vector_index_to_hnsw'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=15, null=True, unique=True),
        ),
    ]
