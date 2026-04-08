import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='QuestTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField()),
                ('description', models.TextField(blank=True, default='')),
                ('quest_type', models.TextField(choices=[('daily', 'Daily Mission'), ('weekly', 'Weekly Challenge'), ('story', 'Story Quest')], db_index=True)),
                ('condition', models.TextField(choices=[('win_battles', 'Win N Battles'), ('achieve_combo', 'Achieve N-Link Combo Chain'), ('open_packs', 'Open N Sticker Packs')])),
                ('condition_value', models.PositiveIntegerField(help_text='Target count or threshold to satisfy the condition.')),
                ('reward_type', models.TextField(choices=[('ryo', 'Ryo'), ('sticker_dust', 'Sticker Dust'), ('sticker_pack', 'Sticker Pack')])),
                ('reward_value', models.PositiveIntegerField(help_text='Primary reward amount (Ryo / Dust / Pack count).')),
                ('reward_dust', models.PositiveIntegerField(default=0, help_text='Secondary Sticker Dust reward (additive, may be 0).')),
                ('is_active', models.BooleanField(db_index=True, default=True)),
                ('order', models.PositiveSmallIntegerField(default=0, help_text='Display order (used for story quests to show unlock sequence).')),
            ],
            options={
                'verbose_name': 'quest template',
                'verbose_name_plural': 'quest templates',
                'ordering': ['quest_type', 'order', 'pk'],
            },
        ),
        migrations.CreateModel(
            name='UserQuest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('period_key', models.CharField(db_index=True, max_length=30)),
                ('progress', models.PositiveIntegerField(default=0)),
                ('completed', models.BooleanField(db_index=True, default=False)),
                ('rewarded', models.BooleanField(default=False)),
                ('assigned_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='quests', to=settings.AUTH_USER_MODEL)),
                ('template', models.ForeignKey(db_index=True, on_delete=django.db.models.deletion.CASCADE, related_name='user_quests', to='quests.questtemplate')),
            ],
            options={
                'verbose_name': 'user quest',
                'verbose_name_plural': 'user quests',
                'ordering': ['template__order', 'assigned_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='userquest',
            constraint=models.UniqueConstraint(
                fields=['user', 'template', 'period_key'],
                name='unique_user_quest_period',
            ),
        ),
    ]
