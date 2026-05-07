from django.db import migrations

ORIGINAL_COSTS = {
    "meadow_route":     200,
    "bamboo_forest":    500,
    "coastal_shallows": 800,
    "mountain_pass":    1500,
    "hidden_ruins":     3000,
    "storm_summit":     5000,
}


def revert_costs(apps, schema_editor):
    Zone = apps.get_model("expedition", "Zone")
    for key, cost in ORIGINAL_COSTS.items():
        Zone.objects.filter(key=key).update(cost=cost)


class Migration(migrations.Migration):

    dependencies = [
        ("expedition", "0002_zone_costs_x10"),
    ]

    operations = [
        migrations.RunPython(revert_costs, migrations.RunPython.noop),
    ]
