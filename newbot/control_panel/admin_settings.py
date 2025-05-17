# control_panel/admin_settings.py
import discord
from utils.logger import log_debug, log_info, log_warning, log_error

class AdminSettingsModal(discord.ui.Modal, title="관리자 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        
        self.admin_ids = discord.ui.TextInput(
            label="관리자 ID 목록 (쉼표로 구분)",
            default=", ".join(bot_config.admin_ids),
            required=True,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.admin_ids)
        
        self.enable_hot_reload = discord.ui.TextInput(
            label="핫 리로딩 활성화 (True/False)",
            default="True" if bot_config.get("enable_hot_reload", True) else "False",
            required=True
        )
        self.add_item(self.enable_hot_reload)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 관리자 ID 파싱
            new_admin_ids = [id.strip() for id in self.admin_ids.value.split(",") if id.strip()]
            
            # 핫 리로딩 설정 파싱
            enable_hot_reload = self.enable_hot_reload.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            
            # 자신의 ID는 항상 포함
            if str(interaction.user.id) not in new_admin_ids:
                new_admin_ids.append(str(interaction.user.id))
            
            # 변경 사항 추적
            old_admin_ids = self.bot_config.admin_ids.copy()
            old_hot_reload = self.bot_config.get("enable_hot_reload", True)
            
            if set(old_admin_ids) != set(new_admin_ids):
                self.bot_config.track_change("admin_ids", "admin_ids", old_admin_ids, new_admin_ids)
            
            if old_hot_reload != enable_hot_reload:
                self.bot_config.track_change("settings", "enable_hot_reload", old_hot_reload, enable_hot_reload)
            
            # 설정 업데이트
            self.bot_config.admin_ids = new_admin_ids
            self.bot_config.enable_hot_reload = enable_hot_reload
            
            # 날씨 시스템에 설정 적용
            weather_cog = interaction.client.get_cog('WeatherCommands')
            if weather_cog and hasattr(weather_cog, 'weather_system'):
                weather_system = weather_cog.weather_system
                if hasattr(weather_system, 'GLOBAL_SETTINGS'):
                    weather_system.GLOBAL_SETTINGS['ADMIN_USER_IDS'] = new_admin_ids
            
            # 설정 저장
            self.bot_config.save()
            
            # 변경 내역 관리자에게 보고
            from .module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            # 결과 메시지
            message = "✅ 관리자 설정이 업데이트되었습니다."
            if old_hot_reload != enable_hot_reload:
                if enable_hot_reload:
                    message += "\n⚠️ 핫 리로딩이 활성화되었습니다. 다음 봇 재시작 시 적용됩니다."
                else:
                    message += "\n⚠️ 핫 리로딩이 비활성화되었습니다. 다음 봇 재시작 시 적용됩니다."
            
            await interaction.response.send_message(message, ephemeral=True)
            self.bot_config.clear_changes()
        except Exception as e:
            log_error(f"관리자 설정 업데이트 중 오류: {e}", e)
            await interaction.response.send_message(f"⚠️ 설정 업데이트 중 오류 발생: {str(e)}", ephemeral=True)

async def handle_admin_settings(interaction, bot, bot_config):
    """관리자 설정 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    # 관리자 설정 모달
    modal = AdminSettingsModal(bot_config)
    await interaction.response.send_modal(modal)

def setup_admin_settings(bot, bot_config):
    """관리자 설정 초기화"""
    log_debug("관리자 설정 모듈 초기화 완료")