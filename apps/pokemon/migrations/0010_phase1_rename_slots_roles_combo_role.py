"""
Phase 1 — Rename & Align

- Renames slot_type values: special→mystery, support→passive_1, passive→passive_2
- Renames primary_role values: dps→burst, assassin→combo, bruiser→tank
- Adds combo_role field to Move
"""
from django.db import migrations, models


def rename_slot_types_forward(apps, schema_editor):
    Move = apps.get_model("pokemon", "Move")
    SpeciesMovePool = apps.get_model("pokemon", "SpeciesMovePool")

    renames = {"special": "mystery", "support": "passive_1", "passive": "passive_2"}
    for old, new in renames.items():
        Move.objects.filter(slot_type=old).update(slot_type=new)
        SpeciesMovePool.objects.filter(slot_type=old).update(slot_type=new)


def rename_slot_types_backward(apps, schema_editor):
    Move = apps.get_model("pokemon", "Move")
    SpeciesMovePool = apps.get_model("pokemon", "SpeciesMovePool")

    renames = {"mystery": "special", "passive_1": "support", "passive_2": "passive"}
    for old, new in renames.items():
        Move.objects.filter(slot_type=old).update(slot_type=new)
        SpeciesMovePool.objects.filter(slot_type=old).update(slot_type=new)


def rename_roles_forward(apps, schema_editor):
    Pokemon = apps.get_model("pokemon", "Pokemon")
    SpeciesMovePool = apps.get_model("pokemon", "SpeciesMovePool")

    Pokemon.objects.filter(primary_role="dps").update(primary_role="burst")
    Pokemon.objects.filter(primary_role="assassin").update(primary_role="combo")
    Pokemon.objects.filter(primary_role="bruiser").update(primary_role="tank")

    SpeciesMovePool.objects.filter(role_tag="dps").update(role_tag="burst")
    SpeciesMovePool.objects.filter(role_tag="assassin").update(role_tag="combo")
    SpeciesMovePool.objects.filter(role_tag="bruiser").update(role_tag="tank")


def rename_roles_backward(apps, schema_editor):
    Pokemon = apps.get_model("pokemon", "Pokemon")
    SpeciesMovePool = apps.get_model("pokemon", "SpeciesMovePool")

    Pokemon.objects.filter(primary_role="burst").update(primary_role="dps")
    Pokemon.objects.filter(primary_role="combo").update(primary_role="assassin")
    # bruiser is gone — backward maps tank→tank (no recovery possible for merged bruiser)

    SpeciesMovePool.objects.filter(role_tag="burst").update(role_tag="dps")
    SpeciesMovePool.objects.filter(role_tag="combo").update(role_tag="assassin")


class Migration(migrations.Migration):

    dependencies = [
        ("pokemon", "0009_tacticalrole_fields"),
    ]

    operations = [
        # 1. Add combo_role field
        migrations.AddField(
            model_name="move",
            name="combo_role",
            field=models.TextField(
                blank=True,
                choices=[
                    ("starter", "Starter"),
                    ("extender", "Extender"),
                    ("amplifier", "Amplifier"),
                    ("finisher", "Finisher"),
                ],
                db_index=True,
                help_text="Role this move plays in a combo chain (starter/extender/amplifier/finisher).",
                null=True,
            ),
        ),
        # 2. Rename slot_type stored values
        migrations.RunPython(rename_slot_types_forward, rename_slot_types_backward),
        # 3. Rename primary_role / role_tag stored values
        migrations.RunPython(rename_roles_forward, rename_roles_backward),
    ]
