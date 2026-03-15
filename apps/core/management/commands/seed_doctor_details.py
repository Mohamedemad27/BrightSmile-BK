from django.core.management.base import BaseCommand

from apps.core.models import DoctorReview, DoctorService
from apps.users.models import Doctor

DOCTOR_DETAILS = {
    'dr.sarah@smilix.com': {
        'bio': 'Dr. Sarah Johnson is a board-certified orthodontist with over 12 years of experience in cosmetic and restorative dentistry. She specializes in Invisalign treatments and dental veneers.',
        'location': 'Downtown Medical Center, New York',
        'working_hours': 'Mon-Fri 9AM-5PM',
        'services': [
            ('Dental Veneers', 800, 90),
            ('Teeth Whitening', 250, 60),
            ('Invisalign Consultation', 150, 45),
            ('Dental Bonding', 350, 60),
        ],
        'reviews': [
            ('Ahmed M.', 5, 'Dr. Sarah is amazing! My veneers look so natural.'),
            ('Lina K.', 5, 'Very professional and gentle. Highly recommend!'),
            ('Omar R.', 4, 'Great results with my whitening treatment.'),
        ],
    },
    'dr.michael@smilix.com': {
        'bio': 'Dr. Michael Chen is a leading cosmetic dentist known for his artistic approach to smile design. He has transformed over 5,000 smiles using the latest techniques.',
        'location': 'Smile Design Studio, Brooklyn',
        'working_hours': 'Mon-Sat 10AM-6PM',
        'services': [
            ('Porcelain Veneers', 900, 120),
            ('Professional Whitening', 300, 60),
            ('Composite Bonding', 400, 45),
            ('Smile Makeover', 2500, 180),
        ],
        'reviews': [
            ('Sara A.', 5, 'The best cosmetic dentist in the city!'),
            ('Youssef H.', 5, 'My smile makeover changed my confidence completely.'),
            ('Nour T.', 4, 'Professional and knowledgeable. Bit pricey but worth it.'),
        ],
    },
    'dr.emily@smilix.com': {
        'bio': 'Dr. Emily Roberts specializes in periodontal care and dental implant placement. She is passionate about helping patients achieve optimal gum health.',
        'location': 'Periodontal Care Center, Manhattan',
        'working_hours': 'Tue-Sat 8AM-4PM',
        'services': [
            ('Dental Implants', 1500, 120),
            ('Deep Cleaning', 200, 60),
            ('Gum Treatment', 350, 45),
            ('Bone Grafting', 800, 90),
        ],
        'reviews': [
            ('Khalid B.', 5, 'My implants feel like real teeth. Incredible work!'),
            ('Fatima Z.', 4, 'Very thorough deep cleaning. My gums feel great.'),
            ('Rami S.', 5, 'Patient and caring doctor. Explains everything clearly.'),
        ],
    },
    'dr.james@smilix.com': {
        'bio': 'Dr. James Wilson is an endodontist with expertise in root canal therapy and dental trauma. He uses advanced microscope-guided techniques for precision treatment.',
        'location': 'Precision Dental Clinic, Queens',
        'working_hours': 'Mon-Fri 9AM-6PM',
        'services': [
            ('Root Canal Treatment', 450, 90),
            ('Retreatment', 600, 120),
            ('Emergency Care', 200, 30),
            ('Dental Crown', 700, 60),
        ],
        'reviews': [
            ('Dina M.', 5, 'Painless root canal! I was so nervous but he made it easy.'),
            ('Ali K.', 5, 'Saved my tooth when others said it had to go.'),
            ('Mona H.', 4, 'Very skilled. The crown fits perfectly.'),
        ],
    },
}


class Command(BaseCommand):
    help = 'Seed doctor details: bio, location, working hours, services, and reviews'

    def handle(self, *args, **options):
        for email, details in DOCTOR_DETAILS.items():
            try:
                doctor = Doctor.objects.get(user__email=email)
            except Doctor.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'{email} not found, skipping.'))
                continue

            # Update doctor fields
            Doctor.objects.filter(user=doctor.user).update(
                bio=details['bio'],
                location=details['location'],
                working_hours=details['working_hours'],
            )

            # Create services
            for name, price, duration in details['services']:
                DoctorService.objects.get_or_create(
                    doctor=doctor,
                    name=name,
                    defaults={'price': price, 'duration_minutes': duration},
                )

            # Create reviews
            for patient_name, rating, comment in details['reviews']:
                DoctorReview.objects.get_or_create(
                    doctor=doctor,
                    patient_name=patient_name,
                    defaults={'rating': rating, 'comment': comment},
                )

            self.stdout.write(f'  Seeded details for {email}')

        self.stdout.write(self.style.SUCCESS('Done.'))
