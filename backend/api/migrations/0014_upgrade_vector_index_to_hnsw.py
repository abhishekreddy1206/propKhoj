from django.db import migrations


class Migration(migrations.Migration):
    """
    Replace IVFFlat index with HNSW for better recall and no reindexing requirement.
    HNSW is superior for real-time applications with datasets up to ~100K rows.
    """

    atomic = False  # Required for CREATE INDEX CONCURRENTLY

    dependencies = [
        ('api', '0013_conversation_summary_and_property_embedding_text'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            DROP INDEX IF EXISTS property_embedding_idx;
            CREATE INDEX CONCURRENTLY IF NOT EXISTS property_embedding_hnsw_idx
            ON api_property
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
            """,
            reverse_sql="""
            DROP INDEX IF EXISTS property_embedding_hnsw_idx;
            CREATE INDEX IF NOT EXISTS property_embedding_idx
            ON api_property
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
            """
        ),
    ]
