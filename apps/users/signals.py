from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='users.Patient')
def set_patient_user_type(sender, instance, created, **kwargs):
    """
    Signal handler to automatically set user.user_type='patient' when a Patient is created.

    Args:
        sender: The model class (Patient)
        instance: The Patient instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created and instance.user.user_type != 'patient':
        instance.user.user_type = 'patient'
        instance.user.save(update_fields=['user_type'])


@receiver(post_save, sender='users.Doctor')
def set_doctor_user_type(sender, instance, created, **kwargs):
    """
    Signal handler to automatically set user.user_type='doctor' when a Doctor is created.

    Args:
        sender: The model class (Doctor)
        instance: The Doctor instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created and instance.user.user_type != 'doctor':
        instance.user.user_type = 'doctor'
        instance.user.save(update_fields=['user_type'])


@receiver(post_save, sender='users.Admin')
def set_admin_user_type(sender, instance, created, **kwargs):
    """
    Signal handler to automatically set user.user_type='admin' and is_staff=True when an Admin is created.

    Args:
        sender: The model class (Admin)
        instance: The Admin instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    if created:
        update_fields = []
        if instance.user.user_type != 'admin':
            instance.user.user_type = 'admin'
            update_fields.append('user_type')
        if not instance.user.is_staff:
            instance.user.is_staff = True
            update_fields.append('is_staff')
        if update_fields:
            instance.user.save(update_fields=update_fields)


@receiver(post_save, sender='users.User')
def create_admin_profile_for_superuser(sender, instance, created, **kwargs):
    """
    Signal handler to automatically create an Admin profile when a superuser is created.

    Args:
        sender: The model class (User)
        instance: The User instance being saved
        created: Boolean indicating if this is a new instance
        **kwargs: Additional keyword arguments
    """
    # Import here to avoid circular imports
    from apps.users.models import Admin

    if created and instance.is_superuser:
        # Check if admin profile doesn't already exist
        if not hasattr(instance, 'admin_profile'):
            Admin.objects.create(user=instance)
