from django.core.management.base import BaseCommand

from apps.core.models import HealthTip

TIPS = [
    ("Brushing Technique", "Brush gently in circular motions for 2 minutes, twice a day for optimal dental health."),
    ("Floss Daily", "Flossing removes up to 40% of plaque that brushing alone cannot reach. Make it a daily habit."),
    ("Stay Hydrated", "Drinking water helps wash away food particles and bacteria, keeping your mouth clean and fresh."),
    ("Limit Sugar Intake", "Reducing sugar intake significantly decreases the risk of tooth decay and cavities."),
    ("Replace Your Toothbrush", "Replace your toothbrush every 3-4 months or when bristles become frayed."),
    ("Use Fluoride Toothpaste", "Fluoride strengthens tooth enamel and helps prevent decay. Always choose fluoride toothpaste."),
    ("Don't Skip Dental Visits", "Visit your dentist every 6 months for checkups and professional cleaning."),
    ("Eat Crunchy Fruits & Veggies", "Apples, carrots, and celery act as natural toothbrushes, stimulating saliva production."),
    ("Avoid Tobacco Products", "Tobacco stains teeth, causes gum disease, and significantly increases risk of oral cancer."),
    ("Protect Your Teeth", "Wear a mouthguard during sports to prevent chipped, broken, or knocked-out teeth."),
    ("Tongue Cleaning", "Gently brush your tongue daily to remove bacteria and keep your breath fresh."),
    ("Limit Acidic Drinks", "Citrus juices, soda, and wine erode enamel. Rinse with water after consuming them."),
    ("Chew Sugar-Free Gum", "Chewing sugar-free gum after meals stimulates saliva flow, which neutralizes acids."),
    ("Night Brushing Matters Most", "Brushing before bed removes the day's buildup of plaque and bacteria."),
    ("Proper Flossing Technique", "Curve the floss into a C-shape around each tooth and slide it under the gumline gently."),
    ("Calcium for Strong Teeth", "Dairy products, leafy greens, and almonds provide calcium essential for strong teeth."),
    ("Avoid Ice Chewing", "Chewing ice can crack or chip teeth and damage dental work. Let ice melt naturally."),
    ("Rinse After Meals", "If you can't brush, rinse your mouth with water after eating to reduce acid and debris."),
    ("Stress Affects Oral Health", "Stress can lead to teeth grinding and jaw clenching. Consider a night guard if needed."),
    ("Smile More Often", "Smiling boosts your mood and confidence. Taking care of your teeth makes smiling effortless!"),
]


class Command(BaseCommand):
    help = "Seed initial health tips into the database"

    def handle(self, *args, **options):
        created = 0
        for title, content in TIPS:
            _, was_created = HealthTip.objects.get_or_create(
                title=title,
                defaults={"content": content},
            )
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(f"Done. Created {created} new health tips ({HealthTip.objects.count()} total).")
        )
