# control_panel/module_views.py
import discord
from typing import Optional, List

from utils.logger import log_debug, log_info, log_warning, log_error
from debug_manager import debug_manager

# 모듈 선택 클래스
class ModuleSelect(discord.ui.Select):
    """모듈 선택 드롭다운"""
    def __init__(self, bot, bot_config, control_panel):
        self.bot = bot
        self.bot_config = bot_config
        self.control_panel = control_panel
        
        options = [
            discord.SelectOption(
                label=module,
                description=f"{'활성화' if state else '비활성화'} 상태",
                value=module,
                default=state
            )
            for module, state in bot_config.modules.items()
        ]
        
        super().__init__(
            placeholder="모듈 선택...",
            min_values=0,
            max_values=len(options),
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if str(interaction.user.id) not in self.bot_config.admin_ids:
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return
        
        # 선택된 모듈 상태 업데이트
        for module in self.bot_config.modules:
            old_state = self.bot_config.modules[module]
            new_state = module in self.values
            
            if old_state != new_state:
                self.bot_config.track_change("modules", module, old_state, new_state)
                self.bot_config.modules[module] = new_state
                
                # 디버그 매니저에 모듈 디버그 설정 업데이트
                debug_manager.set_module_debug(module, new_state)
        
        # 설정 저장
        self.bot_config.save()
        
        # 변경 내용 관리자에게 보고
        if self.bot_config.changed_settings:
            await notify_admins_about_changes(self.bot, self.bot_config)
        
        await interaction.response.send_message("✅ 모듈 상태가 업데이트되었습니다.\n다음 서버 재시작 때 적용됩니다.", ephemeral=True)
        self.bot_config.clear_changes()
        
        # 제어판 업데이트
        await self.control_panel.refresh_message()

# 모듈 관리 기능
async def handle_module_select(interaction: discord.Interaction, bot, bot_config, control_panel):
    """모듈 선택 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    # 모듈 선택 뷰 생성
    view = discord.ui.View(timeout=300)
    view.add_item(ModuleSelect(bot, bot_config, control_panel))
    
    # 모듈 상태 임베드
    embed = discord.Embed(
        title="🧩 모듈 상태 관리",
        description="활성화할 모듈을 선택하세요.",
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def notify_admins_about_changes(bot, bot_config):
    """설정 변경 내역을 관리자들에게 DM으로 보고"""
    if not bot_config.changed_settings:
        return
    
    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 변경 내역 임베드 생성
    embed = discord.Embed(
        title="⚙️ 봇 설정 변경 알림",
        description=f"다음 설정이 변경되었습니다. ({now})",
        color=discord.Color.blue()
    )
    
    # 모듈 변경 사항
    if "modules" in bot_config.changed_settings:
        modules_changes = []
        for module, change in bot_config.changed_settings["modules"].items():
            old_state = "활성화" if change["old"] else "비활성화"
            new_state = "활성화" if change["new"] else "비활성화"
            modules_changes.append(f"`{module}`: {old_state} → {new_state}")
        
        if modules_changes:
            embed.add_field(name="모듈 상태 변경", value="\n".join(modules_changes), inline=False)
    
    # 게임 설정 변경 사항
    if "game_settings" in bot_config.changed_settings:
        for game, settings in bot_config.changed_settings["game_settings"].items():
            game_changes = []
            for setting, change in settings.items():
                game_changes.append(f"`{setting}`: {change['old']} → {change['new']}")
            
            if game_changes:
                embed.add_field(name=f"{game} 설정 변경", value="\n".join(game_changes), inline=False)
    
    # 날씨 설정 변경 사항
    if "weather_settings" in bot_config.changed_settings:
        weather_changes = []
        for setting, change in bot_config.changed_settings["weather_settings"].items():
            weather_changes.append(f"`{setting}`: {change['old']} → {change['new']}")
        
        if weather_changes:
            embed.add_field(name="날씨 시스템 설정 변경", value="\n".join(weather_changes), inline=False)
    
    # 로깅 설정 변경 사항
    if "logging" in bot_config.changed_settings:
        logging_changes = []
        for setting, change in bot_config.changed_settings["logging"].items():
            logging_changes.append(f"`{setting}`: {change['old']} → {change['new']}")
        
        if logging_changes:
            embed.add_field(name="로깅 설정 변경", value="\n".join(logging_changes), inline=False)
    
    # 관리자 ID 변경 사항
    if "admin_ids" in bot_config.changed_settings:
        admin_changes = []
        for setting, change in bot_config.changed_settings["admin_ids"].items():
            if setting == "admin_ids":
                old_ids = ", ".join(change["old"])
                new_ids = ", ".join(change["new"])
                admin_changes.append(f"관리자 ID 목록: {old_ids} → {new_ids}")
        
        if admin_changes:
            embed.add_field(name="관리자 설정 변경", value="\n".join(admin_changes), inline=False)
    
    # 모든 관리자에게 DM 전송
    for admin_id in bot_config.admin_ids:
        try:
            admin_user = await bot.fetch_user(int(admin_id))
            await admin_user.send(embed=embed)
        except Exception as e:
            log_error(f"관리자 {admin_id}에게 DM 전송 중 오류 발생: {e}", e)

def setup_module_views(bot, bot_config):
    """모듈 뷰 초기화"""
    log_debug("모듈 뷰 설정 완료")