from django.db import migrations, models

# Email -> syndicate number mapping for already-seeded doctors. Mirrors the
# bundled syndicate registry fixture so existing demo doctors show their
# membership number in the admin dashboard after this migration runs.
SYNDICATE_BACKFILL = {
    "doctor@smilix.com": "SYN-10001",
    "dr.james@smilix.com": "SYN-10002",
    "dr.emily@smilix.com": "SYN-10003",
    "dr.michael@smilix.com": "SYN-10004",
    "dr.sarah@smilix.com": "SYN-10005",
    "nour.eldin@smilix.com": "SYN-10006",
    "layla.mahmoud@smilix.com": "SYN-10007",
    "karim.saeed@smilix.com": "SYN-10008",
    "hana.mostafa@smilix.com": "SYN-10009",
    "tarek.adel@smilix.com": "SYN-10010",
}


def backfill_syndicate_numbers(apps, schema_editor):
    Doctor = apps.get_model("users", "Doctor")
    for email, syndicate_number in SYNDICATE_BACKFILL.items():
        Doctor.objects.filter(
            user__email__iexact=email
        ).update(syndicate_number=syndicate_number)


def reverse_backfill(apps, schema_editor):
    Doctor = apps.get_model("users", "Doctor")
    Doctor.objects.filter(
        syndicate_number__in=list(SYNDICATE_BACKFILL.values())
    ).update(syndicate_number="")


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_alter_user_user_type_adminrole_adminroleassignment_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="doctor",
            name="syndicate_number",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="Dental syndicate membership number, verified at registration.",
                max_length=50,
            ),
        ),
        migrations.RunPython(backfill_syndicate_numbers, reverse_backfill),
    ]
