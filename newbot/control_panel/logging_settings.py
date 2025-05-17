# control_panel/logging_settings.py
import discord
from utils.logger import log_debug, log_info, log_warning, log_error

class LoggingSettingsModal(discord.ui.Modal, title="로깅 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        
        # 설정 항목
        self.debug_mode = discord.ui.TextInput(
            label="디버그 모드 (True/False)",
            default="True" if bot_config.logging.get("debug_mode", True) else "False",
            required=True
        )
        self.add_item(self.debug_mode)
        
        self.verbose_debug = discord.ui.TextInput(
            label="상세 디버그 (True/False)",
            default="True" if bot_config.logging.get("verbose_debug", True) else "False",
            required=True
        )
        self.add_item(self.verbose_debug)
        
        self.log_commands = discord.ui.TextInput(
            label="명령어 로깅 (True/False)",
            default="True" if bot_config.logging.get("log_commands", True) else "False",
            required=True
        )
        self.add_item(self.log_commands)
        
        self.log_to_file = discord.ui.TextInput(
            label="파일 로깅 (True/False)",
            default="True" if bot_config.logging.get("log_to_file", True) else "False",
            required=True
        )
        self.add_item(self.log_to_file)
        
        self.discord_channel_log = discord.ui.TextInput(
            label="디스코드 채널 로깅 (True/False)",
            default="True" if bot_config.logging.get("discord_channel_log", True) else "False",
            required=True
        )
        self.add_item(self.discord_channel_log)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 원래 값 저장
            old_settings = self.bot_config.logging.copy()
            
            # 입력값 파싱
            new_settings = {
                "debug_mode": self.debug_mode.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"],
                "verbose_debug": self.verbose_debug.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"],
                "log_commands": self.log_commands.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"],
                "log_to_file": self.log_to_file.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"],
                "discord_channel_log": self.discord_channel_log.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            }
            
            # 변경 사항 추적
            for key, new_value in new_settings.items():
                old_value = old_settings.get(key)
                if old_value != new_value:
                    self.bot_config.track_change("logging", key, old_value, new_value)
            
            # 설정 업데이트
            self.bot_config.logging.update(new_settings)
            
            # 설정 저장
            self.bot_config.save()
            
            # 디버그 설정 업데이트
            from utils.logger import setup_logger
            setup_logger(
                self.bot_config.logging.get("log_file", "bot_log.log"),
                new_settings["debug_mode"],
                new_settings["verbose_debug"],
                new_settings["log_to_file"]
            )
            
            # 디버그 매니저 설정 업데이트
            from debug_manager import debug_manager
            debug_manager.toggle_debug_mode(new_settings["debug_mode"])
            debug_manager.toggle_verbose_debug(new_settings["verbose_debug"])
            
            # 변경 내역 관리자에게 보고
            from .module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message("✅ 로깅 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
            
            log_info("로깅 설정이 업데이트되었습니다.")
            log_debug(f"디버그 모드: {new_settings['debug_mode']}, 상세 디버그: {new_settings['verbose_debug']}")
        except Exception as e:
            log_error(f"로깅 설정 업데이트 중 오류: {e}", e)
            await interaction.response.send_message(f"⚠️ 설정 업데이트 중 오류 발생: {str(e)}", ephemeral=True)

async def handle_logging_settings(interaction, bot, bot_config):
    """로깅 설정 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    # 로깅 설정 모달
    modal = LoggingSettingsModal(bot_config)
    await interaction.response.send_modal(modal)

def setup_logging_settings(bot, bot_config):
    """로깅 설정 초기화"""
    log_debug("로깅 설정 모듈 초기화 완료")