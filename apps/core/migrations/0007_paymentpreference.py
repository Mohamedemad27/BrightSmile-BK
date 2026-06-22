import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0006_paymentmethod'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentPreference',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('mobile_wallet_enabled', models.BooleanField(default=False)),
                ('mobile_wallet_provider', models.CharField(blank=True, choices=[('vodafone_cash', 'Vodafone Cash'), ('orange_cash', 'Orange Cash'), ('etisalat_cash', 'Etisalat Cash')], default='', max_length=30)),
                ('cash_on_visit_enabled', models.BooleanField(default=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=models.deletion.CASCADE, related_name='payment_preference', to='users.user')),
            ],
        ),
    ]
