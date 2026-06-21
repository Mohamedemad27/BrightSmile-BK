from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0004_favoritedoctor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentTransaction',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('provider', models.CharField(choices=[('paymob', 'Paymob')], default='paymob', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('paid', 'Paid'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], db_index=True, default='pending', max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('currency', models.CharField(default='EGP', max_length=8)),
                ('checkout_url', models.URLField(blank=True, default='', max_length=1000)),
                ('provider_reference', models.CharField(blank=True, db_index=True, default='', max_length=255)),
                ('client_secret', models.CharField(blank=True, default='', max_length=500)),
                ('provider_payload', models.JSONField(blank=True, default=dict)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('appointment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_transactions', to='core.appointment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payment_transactions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['user', 'status'], name='pay_tx_user_status_idx'),
                    models.Index(fields=['appointment', 'status'], name='pay_tx_appt_status_idx'),
                ],
            },
        ),
    ]
