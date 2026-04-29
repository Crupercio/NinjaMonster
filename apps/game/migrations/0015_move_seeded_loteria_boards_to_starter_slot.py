from django.db import migrations


STARTER_SLOT = 4


def move_seeded_boards_to_starter_slot(apps, schema_editor):
    LoteriaBoardTemplate = apps.get_model("game", "LoteriaBoardTemplate")

    seeded_boards = list(
        LoteriaBoardTemplate.objects.filter(seeded_by_system=True).order_by("owner_id", "deck_key", "created_at", "pk")
    )
    seen_keys = set()
    for board in seeded_boards:
        key = (board.owner_id, board.deck_key)
        if key in seen_keys:
            board.delete()
            continue
        seen_keys.add(key)
        if board.board_slot != STARTER_SLOT:
            board.board_slot = STARTER_SLOT
            board.save(update_fields=["board_slot", "updated_at"])


def move_seeded_boards_back_to_first_slot(apps, schema_editor):
    LoteriaBoardTemplate = apps.get_model("game", "LoteriaBoardTemplate")
    for board in LoteriaBoardTemplate.objects.filter(seeded_by_system=True, board_slot=STARTER_SLOT).order_by("pk"):
        board.board_slot = 1
        board.save(update_fields=["board_slot", "updated_at"])


class Migration(migrations.Migration):

    dependencies = [
        ("game", "0014_loteria_room_host_mode_and_lobby_state"),
    ]

    operations = [
        migrations.RunPython(move_seeded_boards_to_starter_slot, move_seeded_boards_back_to_first_slot),
    ]
