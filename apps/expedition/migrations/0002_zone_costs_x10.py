from django.db import migrations

COST_MAP = {
    "meadow_route":     2000,
    "bamboo_forest":    5000,
    "coastal_shallows": 8000,
    "mountain_pass":    15000,
    "hidden_ruins":     30000,
    "storm_summit":     50000,
}


def update_costs(apps, schema_editor):
    Zone = apps.get_model("expedition", "Zone")
    for key, cost in COST_MAP.items():
        Zone.objects.filter(key=key).update(cost=cost)


class Migration(migrations.Migration):

    dependencies = [
        ("expedition", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(update_costs, migrations.RunPython.noop),
    ]
