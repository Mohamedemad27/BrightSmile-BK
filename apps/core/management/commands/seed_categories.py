from django.core.management.base import BaseCommand

from apps.core.models import ServiceCategory
from apps.users.models import Doctor

CATEGORIES = [
    {'name': 'Veneers', 'icon_name': 'auto_awesome'},
    {'name': 'Whitening', 'icon_name': 'light_mode'},
    {'name': 'Plantation', 'icon_name': 'spa'},
]

# Map doctor emails to their categories
DOCTOR_CATEGORIES = {
    'dr.sarah@smilix.com': ['Veneers', 'Whitening'],
    'dr.michael@smilix.com': ['Whitening', 'Plantation'],
    'dr.emily@smilix.com': ['Veneers', 'Plantation'],
    'dr.james@smilix.com': ['Veneers', 'Whitening', 'Plantation'],
}


class Command(BaseCommand):
    help = 'Seed service categories and assign doctors to them'

    def handle(self, *args, **options):
        # Create categories
        created = 0
        for cat in CATEGORIES:
            _, was_created = ServiceCategory.objects.get_or_create(
                name=cat['name'],
                defaults={'icon_name': cat['icon_name']},
            )
            if was_created:
                created += 1

        self.stdout.write(f'Categories: created {created} new.')

        # Assign doctors to categories
        assigned = 0
        for email, cat_names in DOCTOR_CATEGORIES.items():
            try:
                doctor = Doctor.objects.get(user__email=email)
                cats = ServiceCategory.objects.filter(name__in=cat_names)
                doctor.categories.set(cats)
                assigned += 1
            except Doctor.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Doctor {email} not found, skipping.'))

        self.stdout.write(
            self.style.SUCCESS(f'Done. Assigned categories to {assigned} doctors.')
        )
