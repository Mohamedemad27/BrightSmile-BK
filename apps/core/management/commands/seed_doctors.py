from django.core.management.base import BaseCommand

from apps.users.models import Doctor, User

DOCTORS = [
    {
        'email': 'dr.sarah@smilix.com',
        'first_name': 'Sarah',
        'last_name': 'Johnson',
        'phone_number': '+12125550101',
        'specialty': 'Orthodontics',
        'rating': 4.9,
        'total_reviews': 234,
        'profile_image_url': 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=200&h=200&fit=crop&crop=face',
    },
    {
        'email': 'dr.michael@smilix.com',
        'first_name': 'Michael',
        'last_name': 'Chen',
        'phone_number': '+12125550102',
        'specialty': 'Cosmetic Dentistry',
        'rating': 4.8,
        'total_reviews': 189,
        'profile_image_url': 'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=200&h=200&fit=crop&crop=face',
    },
    {
        'email': 'dr.emily@smilix.com',
        'first_name': 'Emily',
        'last_name': 'Roberts',
        'phone_number': '+12125550103',
        'specialty': 'Periodontics',
        'rating': 4.7,
        'total_reviews': 156,
        'profile_image_url': 'https://images.unsplash.com/photo-1594824476967-48c8b964ac31?w=200&h=200&fit=crop&crop=face',
    },
    {
        'email': 'dr.james@smilix.com',
        'first_name': 'James',
        'last_name': 'Wilson',
        'phone_number': '+12125550104',
        'specialty': 'Endodontics',
        'rating': 4.6,
        'total_reviews': 142,
        'profile_image_url': 'https://images.unsplash.com/photo-1537368910025-700350fe46c7?w=200&h=200&fit=crop&crop=face',
    },
]


class Command(BaseCommand):
    help = 'Seed top-rated doctor profiles'

    def handle(self, *args, **options):
        created = 0
        for doc in DOCTORS:
            if User.objects.filter(email=doc['email']).exists():
                continue

            user = User.objects.create_user(
                email=doc['email'],
                password='DoctorPass123!',
                first_name=doc['first_name'],
                last_name=doc['last_name'],
                user_type='doctor',
                is_active=True,
                is_verified=True,
            )

            Doctor.objects.filter(user=user).update(
                phone_number=doc['phone_number'],
                specialty=doc['specialty'],
                rating=doc['rating'],
                total_reviews=doc['total_reviews'],
                profile_image_url=doc['profile_image_url'],
            )
            # If signal didn't create the Doctor, create it manually
            if not Doctor.objects.filter(user=user).exists():
                Doctor.objects.create(
                    user=user,
                    phone_number=doc['phone_number'],
                    specialty=doc['specialty'],
                    rating=doc['rating'],
                    total_reviews=doc['total_reviews'],
                    profile_image_url=doc['profile_image_url'],
                )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f'Done. Created {created} doctors ({Doctor.objects.count()} total).')
        )
