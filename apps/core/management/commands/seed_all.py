from datetime import date, timedelta

from django.core.management.base import BaseCommand

from apps.core.models import Appointment, DoctorReview, DoctorService, HealthTip, ServiceCategory
from apps.users.models import Doctor, Patient, User


class Command(BaseCommand):
    help = 'Seed all data: users, categories, doctors, services, appointments, reviews, and health tips'

    def handle(self, *args, **options):
        self._seed_categories()
        self._seed_test_patient()
        self._seed_doctors()
        self._seed_appointments()
        self._seed_health_tips()
        self.stdout.write(self.style.SUCCESS('\nAll data seeded successfully.'))

    def _seed_categories(self):
        categories = [
            {'name': 'Veneers', 'icon_name': 'auto_awesome'},
            {'name': 'Whitening', 'icon_name': 'light_mode'},
            {'name': 'Implant', 'icon_name': 'healing'},
        ]
        created = 0
        for cat in categories:
            _, was_created = ServiceCategory.objects.get_or_create(
                name=cat['name'], defaults={'icon_name': cat['icon_name']},
            )
            if was_created:
                created += 1
        self.stdout.write(f'  Categories: {created} created')

    def _seed_test_patient(self):
        if User.objects.filter(email='test@smilix.com').exists():
            self.stdout.write('  Test patient: already exists')
            return

        user = User.objects.create_user(
            email='test@smilix.com',
            password='Test1234!',
            first_name='Test',
            last_name='User',
            user_type='patient',
            is_active=True,
            is_verified=True,
        )
        Patient.objects.get_or_create(
            user=user, defaults={
                'date_of_birth': '1995-01-15',
                'phone_number': '+201234567890',
            },
        )
        self.stdout.write('  Test patient: created (test@smilix.com / Test1234!)')

    def _seed_doctors(self):
        doctors_data = [
            {
                'email': 'dr.sarah@smilix.com',
                'first_name': 'Sarah',
                'last_name': 'Johnson',
                'phone': '+201012345678',
                'rating': 4.9,
                'total_reviews': 3,
                'bio': 'Dr. Sarah Johnson is a board-certified orthodontist with over 12 years of experience in cosmetic and restorative dentistry.',
                'location': 'Downtown Medical Center, Cairo',
                'working_hours': 'Mon-Fri 9AM-5PM',
                'image': 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=200&h=200&fit=crop&crop=face',
                'categories': ['Veneers', 'Whitening'],
                'services': [
                    ('Dental Veneers', 12000),
                    ('Teeth Whitening', 3500),
                    ('Invisalign Consultation', 2000),
                    ('Dental Bonding', 5000),
                ],
            },
            {
                'email': 'dr.michael@smilix.com',
                'first_name': 'Michael',
                'last_name': 'Chen',
                'phone': '+201087654321',
                'rating': 4.8,
                'total_reviews': 2,
                'bio': 'Dr. Michael Chen is a leading cosmetic dentist known for his artistic approach to smile design.',
                'location': 'Smile Design Studio, Heliopolis',
                'working_hours': 'Mon-Sat 10AM-6PM',
                'image': 'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=200&h=200&fit=crop&crop=face',
                'categories': ['Whitening', 'Implant'],
                'services': [
                    ('Porcelain Veneers', 15000),
                    ('Professional Whitening', 4500),
                    ('Composite Bonding', 6000),
                    ('Smile Makeover', 40000),
                ],
            },
            {
                'email': 'dr.emily@smilix.com',
                'first_name': 'Emily',
                'last_name': 'Roberts',
                'phone': '+201155566677',
                'rating': 4.7,
                'total_reviews': 2,
                'bio': 'Dr. Emily Roberts specializes in periodontal care and dental implant placement.',
                'location': 'Periodontal Care Center, Maadi',
                'working_hours': 'Tue-Sat 8AM-4PM',
                'image': 'https://images.unsplash.com/photo-1594824476967-48c8b964ac31?w=200&h=200&fit=crop&crop=face',
                'categories': ['Veneers', 'Implant'],
                'services': [
                    ('Dental Implants', 25000),
                    ('Deep Cleaning', 3000),
                    ('Gum Treatment', 5500),
                    ('Bone Grafting', 12000),
                ],
            },
            {
                'email': 'dr.james@smilix.com',
                'first_name': 'James',
                'last_name': 'Wilson',
                'phone': '+201199988877',
                'rating': 4.6,
                'total_reviews': 1,
                'bio': 'Dr. James Wilson is an endodontist with expertise in root canal therapy and dental trauma.',
                'location': 'Precision Dental Clinic, Nasr City',
                'working_hours': 'Mon-Fri 9AM-6PM',
                'image': 'https://images.unsplash.com/photo-1537368910025-700350fe46c7?w=200&h=200&fit=crop&crop=face',
                'categories': ['Veneers', 'Whitening', 'Implant'],
                'services': [
                    ('Root Canal Treatment', 7000),
                    ('Retreatment', 9000),
                    ('Emergency Care', 3000),
                    ('Dental Crown', 10000),
                ],
            },
        ]

        for doc_data in doctors_data:
            if User.objects.filter(email=doc_data['email']).exists():
                self.stdout.write(f'  Doctor {doc_data["email"]}: already exists')
                continue

            user = User.objects.create_user(
                email=doc_data['email'],
                password='DoctorPass123!',
                first_name=doc_data['first_name'],
                last_name=doc_data['last_name'],
                user_type='doctor',
                is_active=True,
                is_verified=True,
            )

            doctor, _ = Doctor.objects.get_or_create(
                user=user, defaults={'phone_number': doc_data['phone']},
            )
            Doctor.objects.filter(user=user).update(
                phone_number=doc_data['phone'],
                rating=doc_data['rating'],
                total_reviews=doc_data['total_reviews'],
                bio=doc_data['bio'],
                location=doc_data['location'],
                working_hours=doc_data['working_hours'],
                profile_image_url=doc_data['image'],
            )
            doctor.refresh_from_db()
            cats = ServiceCategory.objects.filter(name__in=doc_data['categories'])
            doctor.categories.set(cats)

            for name, price in doc_data['services']:
                DoctorService.objects.get_or_create(
                    doctor=doctor, name=name, defaults={'price': price},
                )

            self.stdout.write(f'  Doctor {doc_data["email"]}: created')

    def _seed_appointments(self):
        if Appointment.objects.exists():
            self.stdout.write('  Appointments: already seeded')
            return

        patient = User.objects.filter(email='test@smilix.com').first()
        if not patient:
            return

        today = date.today()
        doctors = Doctor.objects.all()

        appointments_data = [
            # Completed appointment with Dr. Sarah (has review)
            {
                'doctor': 'dr.sarah@smilix.com',
                'date': today - timedelta(days=14),
                'time_slot': '10:00 AM',
                'status': 'completed',
                'notes': 'Teeth whitening consultation',
                'service_idx': [0, 1],
                'review': (5, 'Dr. Sarah is amazing! My veneers look so natural.'),
            },
            # Completed appointment with Dr. Michael (has review)
            {
                'doctor': 'dr.michael@smilix.com',
                'date': today - timedelta(days=7),
                'time_slot': '2:00 PM',
                'status': 'completed',
                'notes': 'Full whitening session',
                'service_idx': [1],
                'review': (5, 'The best cosmetic dentist in Cairo!'),
            },
            # Confirmed upcoming appointment with Dr. Emily
            {
                'doctor': 'dr.emily@smilix.com',
                'date': today + timedelta(days=5),
                'time_slot': '11:00 AM',
                'status': 'confirmed',
                'notes': 'Deep cleaning needed',
                'service_idx': [1],
                'review': None,
            },
            # Pending appointment with Dr. James
            {
                'doctor': 'dr.james@smilix.com',
                'date': today + timedelta(days=12),
                'time_slot': '3:00 PM',
                'status': 'pending',
                'notes': '',
                'service_idx': [0, 3],
                'review': None,
            },
        ]

        for appt_data in appointments_data:
            try:
                doctor = Doctor.objects.get(user__email=appt_data['doctor'])
            except Doctor.DoesNotExist:
                continue

            services = list(doctor.services.all())
            selected = [services[i] for i in appt_data['service_idx'] if i < len(services)]
            total = sum(s.price for s in selected)

            appt = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                date=appt_data['date'],
                time_slot=appt_data['time_slot'],
                status=appt_data['status'],
                notes=appt_data['notes'],
                total_price=total,
            )
            appt.services.set(selected)

            if appt_data['review'] and appt_data['status'] == 'completed':
                rating, comment = appt_data['review']
                DoctorReview.objects.create(
                    appointment=appt,
                    doctor=doctor,
                    user=patient,
                    rating=rating,
                    comment=comment,
                )

        self.stdout.write(f'  Appointments: {len(appointments_data)} created')

    def _seed_health_tips(self):
        tips = [
            ("Brushing Technique", "Brush gently in circular motions for 2 minutes, twice a day for optimal dental health."),
            ("Floss Daily", "Flossing removes up to 40% of plaque that brushing alone cannot reach."),
            ("Stay Hydrated", "Drinking water helps wash away food particles and bacteria."),
            ("Limit Sugar Intake", "Reducing sugar intake significantly decreases the risk of tooth decay."),
            ("Replace Your Toothbrush", "Replace your toothbrush every 3-4 months or when bristles become frayed."),
            ("Use Fluoride Toothpaste", "Fluoride strengthens tooth enamel and helps prevent decay."),
            ("Don't Skip Dental Visits", "Visit your dentist every 6 months for checkups and professional cleaning."),
            ("Eat Crunchy Fruits & Veggies", "Apples, carrots, and celery act as natural toothbrushes."),
            ("Avoid Tobacco Products", "Tobacco stains teeth, causes gum disease, and increases risk of oral cancer."),
            ("Protect Your Teeth", "Wear a mouthguard during sports to prevent dental injuries."),
            ("Tongue Cleaning", "Gently brush your tongue daily to remove bacteria and keep breath fresh."),
            ("Limit Acidic Drinks", "Citrus juices, soda, and wine erode enamel. Rinse with water after."),
            ("Chew Sugar-Free Gum", "Chewing sugar-free gum after meals stimulates saliva flow."),
            ("Night Brushing Matters Most", "Brushing before bed removes the day's buildup of plaque."),
            ("Proper Flossing Technique", "Curve the floss into a C-shape around each tooth."),
            ("Calcium for Strong Teeth", "Dairy products, leafy greens provide calcium essential for teeth."),
            ("Avoid Ice Chewing", "Chewing ice can crack or chip teeth and damage dental work."),
            ("Rinse After Meals", "If you can't brush, rinse your mouth with water after eating."),
            ("Stress Affects Oral Health", "Stress can lead to teeth grinding. Consider a night guard."),
            ("Smile More Often", "Taking care of your teeth makes smiling effortless!"),
        ]
        created = 0
        for title, content in tips:
            _, was_created = HealthTip.objects.get_or_create(
                title=title, defaults={'content': content},
            )
            if was_created:
                created += 1
        self.stdout.write(f'  Health tips: {created} created ({HealthTip.objects.count()} total)')
