# control_panel/game_settings/mine.py
import discord
from utils.logger import log_debug, log_info, log_warning, log_error
from utils.helpers import safe_int_convert

class MineGeneralSettingsModal(discord.ui.Modal, title="채굴 일반 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        
        # 설정 항목들
        self.mining_cooldown = discord.ui.TextInput(
            label="채굴 쿨타임 (초)",
            default=str(bot_config.game_settings['mine']['cooldown']),
            required=True
        )
        self.add_item(self.mining_cooldown)
        
        self.rock_display_time = discord.ui.TextInput(
            label="돌 표시 시간 (초)",
            default=str(bot_config.game_settings['mine']['card_display_time']),
            required=True
        )
        self.add_item(self.rock_display_time)
        
        self.memory_game_time = discord.ui.TextInput(
            label="기억 게임 시간 (초)",
            default=str(bot_config.game_settings['mine']['memory_time']),
            required=True
        )
        self.add_item(self.memory_game_time)
    
    async def on_submit(self, interaction):
        try:
            # 입력값 파싱
            cooldown = safe_int_convert(self.mining_cooldown.value, 3600)
            display_time = safe_int_convert(self.rock_display_time.value, 5)
            memory_time = safe_int_convert(self.memory_game_time.value, 30)
            
            # 유효성 검사
            if cooldown < 0:
                await interaction.response.send_message("⚠️ 쿨타임은 0 이상이어야 합니다.", ephemeral=True)
                return
            
            if display_time < 1:
                await interaction.response.send_message("⚠️ 돌 표시 시간은 1초 이상이어야 합니다.", ephemeral=True)
                return
            
            if memory_time < 5:
                await interaction.response.send_message("⚠️ 기억 게임 시간은 5초 이상이어야 합니다.", ephemeral=True)
                return
            
            # 변경 내역 추적
            old_cooldown = self.bot_config.game_settings['mine']['cooldown']
            old_display_time = self.bot_config.game_settings['mine']['card_display_time']
            old_memory_time = self.bot_config.game_settings['mine']['memory_time']
            
            if old_cooldown != cooldown:
                self.bot_config.track_change("game_settings", "mine", old_cooldown, cooldown, "cooldown")
            if old_display_time != display_time:
                self.bot_config.track_change("game_settings", "mine", old_display_time, display_time, "card_display_time")
            if old_memory_time != memory_time:
                self.bot_config.track_change("game_settings", "mine", old_memory_time, memory_time, "memory_time")
            
            # 설정 업데이트
            self.bot_config.game_settings['mine']['cooldown'] = cooldown
            self.bot_config.game_settings['mine']['card_display_time'] = display_time
            self.bot_config.game_settings['mine']['memory_time'] = memory_time
            
            # 설정 저장
            self.bot_config.save()
            
            # 변경 내역 관리자에게 보고
            from ..module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message("✅ 채굴 일반 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 설정 업데이트 중 오류 발생: {str(e)}", ephemeral=True)

class MineTimeAdjustSettingsModal(discord.ui.Modal, title="채굴 시간 조정 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        
        # 장소별 시간 조정 설정
        self.mine_time_adjust = discord.ui.TextInput(
            label="광산 시간 조정 (초, 음수만 입력)",
            default=str(bot_config.game_settings['mine']['location_time_adjust'].get('광산', 0)),
            required=True
        )
        self.add_item(self.mine_time_adjust)
        
        self.deep_mine_time_adjust = discord.ui.TextInput(
            label="깊은광산 시간 조정 (초, 음수만 입력)",
            default=str(bot_config.game_settings['mine']['location_time_adjust'].get('깊은광산', -5)),
            required=True
        )
        self.add_item(self.deep_mine_time_adjust)
        
        self.ancient_mine_time_adjust = discord.ui.TextInput(
            label="고대광산 시간 조정 (초, 음수만 입력)",
            default=str(bot_config.game_settings['mine']['location_time_adjust'].get('고대광산', -10)),
            required=True
        )
        self.add_item(self.ancient_mine_time_adjust)
    
    async def on_submit(self, interaction):
        try:
            # 입력값 파싱
            mine_adjust = safe_int_convert(self.mine_time_adjust.value, 0)
            deep_mine_adjust = safe_int_convert(self.deep_mine_time_adjust.value, -5)
            ancient_mine_adjust = safe_int_convert(self.ancient_mine_time_adjust.value, -10)
            
            # 유효성 검사 - 음수만 허용
            if mine_adjust > 0:
                await interaction.response.send_message("⚠️ 시간 조정값은 0 이하의 음수만 입력할 수 있습니다.", ephemeral=True)
                return
                
            if deep_mine_adjust > 0:
                await interaction.response.send_message("⚠️ 시간 조정값은 0 이하의 음수만 입력할 수 있습니다.", ephemeral=True)
                return
                
            if ancient_mine_adjust > 0:
                await interaction.response.send_message("⚠️ 시간 조정값은 0 이하의 음수만 입력할 수 있습니다.", ephemeral=True)
                return
            
            # 변경 내역 추적
            old_mine_adjust = self.bot_config.game_settings['mine']['location_time_adjust'].get('광산', 0)
            old_deep_mine_adjust = self.bot_config.game_settings['mine']['location_time_adjust'].get('깊은광산', -5)
            old_ancient_mine_adjust = self.bot_config.game_settings['mine']['location_time_adjust'].get('고대광산', -10)
            
            if old_mine_adjust != mine_adjust:
                self.bot_config.track_change("game_settings", "mine", old_mine_adjust, mine_adjust, "location_time_adjust.광산")
            if old_deep_mine_adjust != deep_mine_adjust:
                self.bot_config.track_change("game_settings", "mine", old_deep_mine_adjust, deep_mine_adjust, "location_time_adjust.깊은광산")
            if old_ancient_mine_adjust != ancient_mine_adjust:
                self.bot_config.track_change("game_settings", "mine", old_ancient_mine_adjust, ancient_mine_adjust, "location_time_adjust.고대광산")
            
            # 설정 업데이트
            self.bot_config.game_settings['mine']['location_time_adjust'] = {
                '광산': mine_adjust,
                '깊은광산': deep_mine_adjust,
                '고대광산': ancient_mine_adjust
            }
            
            # 설정 저장
            self.bot_config.save()
            
            # 변경 내역 관리자에게 보고
            from ..module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message("✅ 채굴 시간 조정 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 설정 업데이트 중 오류 발생: {str(e)}", ephemeral=True)

class MineRockCountSettingsModal(discord.ui.Modal, title="채굴 돌 갯수 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        
        # rock_count가 아직 설정에 없으면 추가
        if 'rock_count' not in self.bot_config.game_settings['mine']:
            self.bot_config.game_settings['mine']['rock_count'] = {
                '광산': 5,
                '깊은광산': 5,
                '고대광산': 5
            }
        
        # 장소별 돌 갯수 설정
        self.mine_rock_count = discord.ui.TextInput(
            label="광산 돌 갯수 (1-25)",
            default=str(self.bot_config.game_settings['mine']['rock_count'].get('광산', 5)),
            required=True
        )
        self.add_item(self.mine_rock_count)
        
        self.deep_mine_rock_count = discord.ui.TextInput(
            label="깊은광산 돌 갯수 (1-25)",
            default=str(self.bot_config.game_settings['mine']['rock_count'].get('깊은광산', 5)),
            required=True
        )
        self.add_item(self.deep_mine_rock_count)
        
        self.ancient_mine_rock_count = discord.ui.TextInput(
            label="고대광산 돌 갯수 (1-25)",
            default=str(self.bot_config.game_settings['mine']['rock_count'].get('고대광산', 5)),
            required=True
        )
        self.add_item(self.ancient_mine_rock_count)
    
    async def on_submit(self, interaction):
        try:
            # 입력값 파싱
            mine_count = safe_int_convert(self.mine_rock_count.value, 5)
            deep_mine_count = safe_int_convert(self.deep_mine_rock_count.value, 5)
            ancient_mine_count = safe_int_convert(self.ancient_mine_rock_count.value, 5)
            
            # 유효성 검사 (1-25 범위)
            if mine_count < 1 or mine_count > 25:
                await interaction.response.send_message("⚠️ 돌 갯수는 1개 이상 25개 이하여야 합니다.", ephemeral=True)
                return
            
            if deep_mine_count < 1 or deep_mine_count > 25:
                await interaction.response.send_message("⚠️ 돌 갯수는 1개 이상 25개 이하여야 합니다.", ephemeral=True)
                return
            
            if ancient_mine_count < 1 or ancient_mine_count > 25:
                await interaction.response.send_message("⚠️ 돌 갯수는 1개 이상 25개 이하여야 합니다.", ephemeral=True)
                return
            
            # 변경 내역 추적
            old_mine_count = self.bot_config.game_settings['mine']['rock_count'].get('광산', 5)
            old_deep_mine_count = self.bot_config.game_settings['mine']['rock_count'].get('깊은광산', 5)
            old_ancient_mine_count = self.bot_config.game_settings['mine']['rock_count'].get('고대광산', 5)
            
            if old_mine_count != mine_count:
                self.bot_config.track_change("game_settings", "mine", old_mine_count, mine_count, "rock_count.광산")
            if old_deep_mine_count != deep_mine_count:
                self.bot_config.track_change("game_settings", "mine", old_deep_mine_count, deep_mine_count, "rock_count.깊은광산")
            if old_ancient_mine_count != ancient_mine_count:
                self.bot_config.track_change("game_settings", "mine", old_ancient_mine_count, ancient_mine_count, "rock_count.고대광산")
            
            # 설정 업데이트
            self.bot_config.game_settings['mine']['rock_count'] = {
                '광산': mine_count,
                '깊은광산': deep_mine_count,
                '고대광산': ancient_mine_count
            }
            
            # 설정 저장
            self.bot_config.save()
            
            # 변경 내역 관리자에게 보고
            from ..module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message("✅ 채굴 돌 갯수 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
        except Exception as e:
            await interaction.response.send_message(f"⚠️ 설정 업데이트 중 오류 발생: {str(e)}", ephemeral=True)

async def handle_mine_settings(interaction, bot, bot_config):
    """채굴 설정 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="⛏️ 채굴 게임 설정",
        description="설정 카테고리를 선택하세요.",
        color=discord.Color.green()
    )
    
    # 현재 설정 정보 표시
    general_settings = [
        f"쿨타임: {bot_config.game_settings['mine']['cooldown']}초",
        f"돌 표시 시간: {bot_config.game_settings['mine']['card_display_time']}초",
        f"기억 게임 시간: {bot_config.game_settings['mine']['memory_time']}초"
    ]
    embed.add_field(name="일반 설정", value="\n".join(general_settings), inline=False)
    
    time_settings = [
        f"광산 시간 조정: {bot_config.game_settings['mine']['location_time_adjust'].get('광산', 0)}초",
        f"깊은광산 시간 조정: {bot_config.game_settings['mine']['location_time_adjust'].get('깊은광산', -5)}초",
        f"고대광산 시간 조정: {bot_config.game_settings['mine']['location_time_adjust'].get('고대광산', -10)}초"
    ]
    embed.add_field(name="시간 조정 설정 (음수만 가능)", value="\n".join(time_settings), inline=False)
    
    # rock_count가 설정에 없으면 기본값 표시
    rock_count = bot_config.game_settings['mine'].get('rock_count', {
        '광산': 5,
        '깊은광산': 5,
        '고대광산': 5
    })
    
    count_settings = [
        f"광산 돌 갯수: {rock_count.get('광산', 5)}개",
        f"깊은광산 돌 갯수: {rock_count.get('깊은광산', 5)}개",
        f"고대광산 돌 갯수: {rock_count.get('고대광산', 5)}개"
    ]
    embed.add_field(name="돌 갯수 설정 (1-25)", value="\n".join(count_settings), inline=False)
    
    view = discord.ui.View(timeout=300)
    
    # 일반 설정 버튼
    general_button = discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="일반설정",
        custom_id="mine_general"
    )
    general_button.callback = lambda i: show_mine_general_settings(i, bot_config)
    view.add_item(general_button)
    
    # 시간 조정 설정 버튼
    time_button = discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="시간설정",
        custom_id="mine_time"
    )
    time_button.callback = lambda i: show_mine_time_settings(i, bot_config)
    view.add_item(time_button)
    
    # 돌 갯수 설정 버튼
    count_button = discord.ui.Button(
        style=discord.ButtonStyle.primary,
        label="갯수설정",
        custom_id="mine_count"
    )
    count_button.callback = lambda i: show_mine_count_settings(i, bot_config)
    view.add_item(count_button)
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def show_mine_general_settings(interaction, bot_config):
    """채굴 일반 설정 모달 표시"""
    modal = MineGeneralSettingsModal(bot_config)
    await interaction.response.send_modal(modal)

async def show_mine_time_settings(interaction, bot_config):
    """채굴 시간 조정 설정 모달 표시"""
    modal = MineTimeAdjustSettingsModal(bot_config)
    await interaction.response.send_modal(modal)

async def show_mine_count_settings(interaction, bot_config):
    """채굴 돌 갯수 설정 모달 표시"""
    modal = MineRockCountSettingsModal(bot_config)
    await interaction.response.send_modal(modal)