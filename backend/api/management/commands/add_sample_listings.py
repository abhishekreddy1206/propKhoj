from django.core.management.base import BaseCommand
from api.models import Property
import random

class Command(BaseCommand):
    help = 'Adds sample property listings'

    def handle(self, *args, **kwargs):
        for i in range(20):
            Property.objects.create(
                property_id=f"PROP{i+1}",
                title=f"Sample Property {i+1}",
                description=f"This is a sample property description for property {i+1}.",
                location=f"Sample Location {i+1}",
                latitude=random.uniform(8.4, 37.6),
                longitude=random.uniform(68.7, 97.25),
                price=random.randint(1000000, 10000000),
                bedrooms=random.randint(1, 5),
                bathrooms=random.randint(1, 4),
                parking_spaces=random.randint(0, 2),
                age_of_property=random.randint(0, 20),
                furnished=random.choice([True, False]),
                size=random.randint(500, 5000),
                property_type=random.choice(['house_buy', 'house_rent', 'land_buy', 'commercial_office_space'])
            )
        self.stdout.write(self.style.SUCCESS('Successfully added sample listings'))
