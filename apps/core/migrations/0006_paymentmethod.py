import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0005_paymenttransaction'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentMethod',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('brand', models.CharField(choices=[('visa', 'Visa'), ('mastercard', 'Mastercard')], max_length=20)),
                ('last4', models.CharField(max_length=4)),
                ('holder_name', models.CharField(max_length=120)),
                ('expiry', models.CharField(max_length=7)),
                ('is_default', models.BooleanField(db_index=True, default=False)),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='payment_methods', to='users.user')),
            ],
            options={
                'ordering': ['-is_default', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='paymentmethod',
            index=models.Index(fields=['user', 'is_active'], name='pay_method_user_active_idx'),
        ),
        migrations.AddIndex(
            model_name='paymentmethod',
            index=models.Index(fields=['user', 'is_default'], name='pay_method_user_default_idx'),
        ),
    ]
