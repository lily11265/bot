# control_panel/game_settings/blackjack.py
import discord
from utils.logger import log_debug, log_info, log_warning, log_error
from utils.helpers import safe_float_convert

class BlackjackSettingsModal(discord.ui.Modal, title="블랙잭 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        blackjack_settings = bot_config.game_settings['blackjack']
        
        self.debug_mode = discord.ui.TextInput(
            label="디버그 모드 (True/False)",
            default="True" if blackjack_settings.get('debug_mode', False) else "False",
            required=True
        )
        self.add_item(self.debug_mode)
        
        self.dealer_bust_chance = discord.ui.TextInput(
            label="딜러 버스트 확률 (0-1)",
            default=str(blackjack_settings.get('dealer_bust_chance', 0.3)),
            required=True
        )
        self.add_item(self.dealer_bust_chance)
        
        self.dealer_low_card_chance = discord.ui.TextInput(
            label="딜러 낮은 카드 확률 (0-1)",
            default=str(blackjack_settings.get('dealer_low_card_chance', 0.4)),
            required=True
        )
        self.add_item(self.dealer_low_card_chance)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 설정값 파싱
            debug_mode = self.debug_mode.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            
            # 확률 파싱
            dealer_bust_chance = safe_float_convert(self.dealer_bust_chance.value, 0.3)
            dealer_low_card_chance = safe_float_convert(self.dealer_low_card_chance.value, 0.4)
            
            # 확률 범위 검증
            if not (0 <= dealer_bust_chance <= 1):
                await interaction.response.send_message("⚠️ 딜러 버스트 확률은 0에서 1 사이여야 합니다.", ephemeral=True)
                return
                
            if not (0 <= dealer_low_card_chance <= 1):
                await interaction.response.send_message("⚠️ 딜러 낮은 카드 확률은 0에서 1 사이여야 합니다.", ephemeral=True)
                return
            
            # 값 업데이트
            old_settings = self.bot_config.game_settings['blackjack'].copy()
            
            self.bot_config.game_settings['blackjack']['debug_mode'] = debug_mode
            self.bot_config.game_settings['blackjack']['dealer_bust_chance'] = dealer_bust_chance
            self.bot_config.game_settings['blackjack']['dealer_low_card_chance'] = dealer_low_card_chance
            
            # 변경 내역 추적
            for key, new_value in self.bot_config.game_settings['blackjack'].items():
                old_value = old_settings.get(key)
                if old_value != new_value:
                    self.bot_config.track_change("game_settings", "blackjack", old_value, new_value, key)
            
            # 설정 저장
            self.bot_config.save()
            
            # 블랙잭 모듈에 설정 적용
            try:
                import blackjack
                if hasattr(blackjack, 'DEBUG_MODE'):
                    blackjack.DEBUG_MODE = debug_mode
                
                if hasattr(blackjack, 'DEALER_BUST_BASE_CHANCE'):
                    blackjack.DEALER_BUST_BASE_CHANCE = dealer_bust_chance
                
                if hasattr(blackjack, 'DEALER_LOW_CARD_BASE_CHANCE'):
                    blackjack.DEALER_LOW_CARD_BASE_CHANCE = dealer_low_card_chance
            except ImportError:
                log_warning("블랙잭 모듈을 가져올 수 없습니다. 설정만 저장됨.")
            
            # 변경 내역 관리자에게 보고
            from ..module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message("✅ 블랙잭 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
            
        except Exception as e:
            log_error(f"블랙잭 설정 업데이트 중 오류: {e}", e)
            await interaction.response.send_message(f"⚠️ 설정 업데이트 중 오류 발생: {str(e)}", ephemeral=True)

async def handle_blackjack_settings(interaction, bot, bot_config):
    """블랙잭 설정 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    # 블랙잭 설정 모달
    modal = BlackjackSettingsModal(bot_config)
    await interaction.response.send_modal(modal)