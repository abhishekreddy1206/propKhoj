import hashlib
from django.core.management.base import BaseCommand
from api.models import Property


class Command(BaseCommand):
    help = 'Regenerate embeddings for all properties'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regenerate all embeddings regardless of content hash',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of properties to process per batch (default: 50)',
        )

    def handle(self, *args, **options):
        force = options['force']
        batch_size = options['batch_size']

        queryset = Property.objects.all()
        total = queryset.count()
        self.stdout.write(f"Processing {total} properties (force={force}, batch_size={batch_size})")

        success = 0
        skipped = 0
        errors = 0

        for i, prop in enumerate(queryset.iterator(chunk_size=batch_size)):
            try:
                text = Property.objects.generate_property_text(prop)
                content_hash = hashlib.sha256(text.encode()).hexdigest()

                if not force and content_hash == prop.embedding_content_hash and prop.embedding:
                    skipped += 1
                    continue

                if Property.objects.update_embedding(prop):
                    prop.embedding_content_hash = content_hash
                    prop.save(skip_embedding=True, update_fields=['embedding_content_hash'])
                    success += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                self.stderr.write(f"Error for property {prop.property_id}: {e}")

            if (i + 1) % batch_size == 0:
                self.stdout.write(f"  Progress: {i + 1}/{total}")

        self.stdout.write(self.style.SUCCESS(
            f"Done. Success: {success}, Skipped: {skipped}, Errors: {errors}"
        ))
