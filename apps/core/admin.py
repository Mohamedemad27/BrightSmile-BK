from django.contrib import admin

from .models import Appointment, DoctorReview, DoctorService, FavoriteDoctor, HealthTip, MedicalHistory, Notification, ServiceCategory


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'icon_name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(DoctorService)
class DoctorServiceAdmin(admin.ModelAdmin):
    list_display = ('id', 'doctor', 'name', 'price')
    search_fields = ('name',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'patient', 'doctor', 'date', 'time_slot', 'status', 'total_price')
    list_filter = ('status', 'date')
    search_fields = ('patient__email', 'doctor__user__email')


@admin.register(DoctorReview)
class DoctorReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'doctor', 'user', 'rating', 'created_at')
    list_filter = ('rating',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'title', 'notif_type', 'is_read', 'created_at')
    list_filter = ('notif_type', 'is_read')


@admin.register(HealthTip)
class HealthTipAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'content')


@admin.register(MedicalHistory)
class MedicalHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'diabetes', 'heart_disease', 'blood_pressure', 'allergies', 'created_at')
    search_fields = ('user__email',)


@admin.register(FavoriteDoctor)
class FavoriteDoctorAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'doctor', 'created_at')
    search_fields = ('user__email', 'doctor__user__email')
