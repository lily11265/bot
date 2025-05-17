# control_panel/game_settings/judgment.py
import discord
from utils.logger import log_debug, log_info, log_warning, log_error

class JudgmentSettingsModal(discord.ui.Modal, title="판정 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        judgment_settings = bot_config.game_settings['judgment']
        
        self.debug_mode = discord.ui.TextInput(
            label="디버그 모드 (True/False)",
            default="True" if judgment_settings.get('debug_mode', False) else "False",
            required=True
        )
        self.add_item(self.debug_mode)
        
        self.enable_ephemeral = discord.ui.TextInput(
            label="Ephemeral 메시지 활성화 (True/False)",
            default="True" if judgment_settings.get('enable_ephemeral_messages', True) else "False",
            required=True
        )
        self.add_item(self.enable_ephemeral)
        
        self.spreadsheet_id = discord.ui.TextInput(
            label="Google 스프레드시트 ID",
            default=str(judgment_settings.get('spreadsheet_id', '')),
            required=False,
            placeholder="스프레드시트 URL에서 ID 부분만 입력"
        )
        self.add_item(self.spreadsheet_id)
        
        self.great_failure = discord.ui.TextInput(
            label="대실패 기준값 (1-100)",
            default=str(judgment_settings.get('great_failure_threshold', 10)),
            required=True
        )
        self.add_item(self.great_failure)
        
        self.success_threshold = discord.ui.TextInput(
            label="대성공 기준값 (1-100)",
            default=str(judgment_settings.get('success_threshold', 90)),
            required=True
        )
        self.add_item(self.success_threshold)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 설정값 파싱
            debug_mode = self.debug_mode.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            enable_ephemeral = self.enable_ephemeral.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            spreadsheet_id = self.spreadsheet_id.value.strip()
            
            # 숫자 검증
            try:
                great_failure = int(self.great_failure.value)
                if not (1 <= great_failure <= 100):
                    raise ValueError("대실패 기준값은 1-100 사이여야 합니다.")
            except ValueError:
                await interaction.response.send_message("⚠️ 대실패 기준값은 1-100 사이의 정수여야 합니다.", ephemeral=True)
                return
                
            try:
                success_threshold = int(self.success_threshold.value)
                if not (1 <= success_threshold <= 100):
                    raise ValueError("대성공 기준값은 1-100 사이여야 합니다.")
            except ValueError:
                await interaction.response.send_message("⚠️ 대성공 기준값은 1-100 사이의 정수여야 합니다.", ephemeral=True)
                return
            
            # 값 업데이트
            old_settings = self.bot_config.game_settings['judgment'].copy()
            
            self.bot_config.game_settings['judgment']['debug_mode'] = debug_mode
            self.bot_config.game_settings['judgment']['enable_ephemeral_messages'] = enable_ephemeral
            self.bot_config.game_settings['judgment']['spreadsheet_id'] = spreadsheet_id
            self.bot_config.game_settings['judgment']['great_failure_threshold'] = great_failure
            self.bot_config.game_settings['judgment']['success_threshold'] = success_threshold
            
            # 실패 기준값은 자동 계산 (대실패와 대성공 사이의 중간값)
            failure_threshold = (great_failure + success_threshold) // 2
            self.bot_config.game_settings['judgment']['failure_threshold'] = failure_threshold
            
            # 변경 내역 추적
            for key, new_value in self.bot_config.game_settings['judgment'].items():
                old_value = old_settings.get(key)
                if old_value != new_value:
                    self.bot_config.track_change("game_settings", "judgment", old_value, new_value, key)
            
            # 설정 저장
            self.bot_config.save()
            
            # 판정 모듈에 설정 적용
            judgment_cog = interaction.client.get_cog('JudgmentCommands')
            if judgment_cog:
                # 디버그 모드 설정
                import judgment
                judgment.DEBUG_MODE = debug_mode
                
                # Ephemeral 메시지 설정
                judgment.ENABLE_EPHEMERAL_MESSAGES = enable_ephemeral
                
                # 설정값 변경
                judgment.GREAT_FAILURE_THRESHOLD = great_failure
                judgment.SUCCESS_THRESHOLD = success_threshold
                judgment.FAILURE_THRESHOLD = failure_threshold
                
                # Ephemeral 관리자 설정 업데이트
                if hasattr(judgment_cog, 'ephemeral_manager'):
                    judgment_cog.ephemeral_manager.enabled = enable_ephemeral
                    judgment_cog.ephemeral_manager.SPREADSHEET_ID = spreadsheet_id
                    judgment_cog.ephemeral_manager.save_config()
            
            # 변경 내역 관리자에게 보고
            from ..module_views import notify_admins_about_changes 
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message("✅ 판정 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
            
        except Exception as e:
            log_error(f"판정 설정 업데이트 중 오류: {e}", e)
            await interaction.response.send_message(f"⚠️ 설정 업데이트 중 오류 발생: {str(e)}", ephemeral=True)

async def handle_judgment_settings(interaction, bot, bot_config):
    """판정 설정 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    # 판정 설정 모달
    modal = JudgmentSettingsModal(bot_config)
    await interaction.response.send_modal(modal)