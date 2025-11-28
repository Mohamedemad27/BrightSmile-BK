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
