import uuid

from django.db import models


class ServiceCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    icon_name = models.CharField(max_length=50, blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Service Categories'

    def __str__(self):
        return self.name


class DoctorService(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey(
        'users.Doctor',
        on_delete=models.CASCADE,
        related_name='services',
    )
    name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} - {self.price} EGP'


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='appointments_as_patient',
        limit_choices_to={'user_type': 'patient'},
    )
    doctor = models.ForeignKey(
        'users.Doctor',
        on_delete=models.CASCADE,
        related_name='appointments',
    )
    services = models.ManyToManyField(DoctorService, related_name='appointments')
    date = models.DateField()
    time_slot = models.CharField(max_length=20)
    notes = models.TextField(max_length=500, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['patient', 'status'], name='appt_patient_status_idx'),
            models.Index(fields=['doctor', 'status'], name='appt_doctor_status_idx'),
            models.Index(fields=['date', 'status'], name='appt_date_status_idx'),
        ]

    def __str__(self):
        return f'{self.patient.get_full_name()} → Dr. {self.doctor.full_name} on {self.date}'


class DoctorReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='review',
    )
    doctor = models.ForeignKey(
        'users.Doctor',
        on_delete=models.CASCADE,
        related_name='reviews',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='reviews_given',
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.get_full_name()} - {self.rating}/5'

    @property
    def patient_name(self):
        return self.user.get_full_name()


class Notification(models.Model):
    NOTIF_TYPES = [
        ('appointment', 'Appointment'),
        ('review', 'Review'),
        ('system', 'System'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='notifications',
    )
    title = models.CharField(max_length=200)
    body = models.TextField(max_length=500)
    notif_type = models.CharField(max_length=20, choices=NOTIF_TYPES, default='system')
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} → {self.user.email}'


class HealthTip(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=100)
    content = models.TextField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.title


class MedicalHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='medical_history',
        limit_choices_to={'user_type': 'patient'},
    )
    diabetes = models.BooleanField(default=False)
    heart_disease = models.BooleanField(default=False)
    blood_pressure = models.BooleanField(default=False)
    allergies = models.BooleanField(default=False)
    bleeding_disorders = models.BooleanField(default=False)
    asthma = models.BooleanField(default=False)
    pregnancy = models.BooleanField(default=False)
    smoking = models.BooleanField(default=False)
    previous_dental_surgery = models.BooleanField(default=False)
    notes = models.TextField(max_length=1000, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Medical History'
        verbose_name_plural = 'Medical Histories'

    def __str__(self):
        return f"Medical History for {self.user.email}"


class FavoriteDoctor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='favorite_doctors',
    )
    doctor = models.ForeignKey(
        'users.Doctor',
        on_delete=models.CASCADE,
        related_name='favorited_by',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'doctor')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} → {self.doctor.full_name}"



class PaymentTransaction(models.Model):
    PROVIDER_CHOICES = [
        ('paymob', 'Paymob'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='payment_transactions',
    )
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='payment_transactions',
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='paymob')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=8, default='EGP')
    checkout_url = models.URLField(max_length=1000, blank=True, default='')
    provider_reference = models.CharField(max_length=255, blank=True, default='', db_index=True)
    client_secret = models.CharField(max_length=500, blank=True, default='')
    provider_payload = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status'], name='pay_tx_user_status_idx'),
            models.Index(fields=['appointment', 'status'], name='pay_tx_appt_status_idx'),
        ]

    def __str__(self):
        return f'{self.user.email} {self.provider} {self.status} {self.amount} {self.currency}'


class PaymentMethod(models.Model):
    BRAND_CHOICES = [
        ('visa', 'Visa'),
        ('mastercard', 'Mastercard'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='payment_methods',
    )
    brand = models.CharField(max_length=20, choices=BRAND_CHOICES)
    last4 = models.CharField(max_length=4)
    holder_name = models.CharField(max_length=120)
    expiry = models.CharField(max_length=7)
    is_default = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']
        indexes = [
            models.Index(fields=['user', 'is_active'], name='pay_method_user_active_idx'),
            models.Index(fields=['user', 'is_default'], name='pay_method_user_default_idx'),
        ]

    def __str__(self):
        return f'{self.user.email} {self.brand} ****{self.last4}'


class PaymentPreference(models.Model):
    WALLET_PROVIDER_CHOICES = [
        ('vodafone_cash', 'Vodafone Cash'),
        ('orange_cash', 'Orange Cash'),
        ('etisalat_cash', 'Etisalat Cash'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        'users.User',
        on_delete=models.CASCADE,
        related_name='payment_preference',
    )
    mobile_wallet_enabled = models.BooleanField(default=False)
    mobile_wallet_provider = models.CharField(
        max_length=30,
        choices=WALLET_PROVIDER_CHOICES,
        blank=True,
        default='',
    )
    cash_on_visit_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.email} wallet={self.mobile_wallet_provider or "off"} cash={self.cash_on_visit_enabled}'
