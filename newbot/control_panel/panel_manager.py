# control_panel/panel_manager.py
import discord
import datetime
from typing import Optional

from utils.logger import log_debug, log_info, log_warning, log_error
from debug_manager import debug_manager

# 제어판 뷰 (중앙 관리)
class ControlPanelView(discord.ui.View):
    """제어판 뷰"""
    def __init__(self, bot, bot_config):
        super().__init__(timeout=None)  # 시간 제한 없음
        self.bot = bot
        self.bot_config = bot_config
        self.message = None
        self.refresh_buttons()
    
    def refresh_buttons(self):
        """버튼 새로고침"""
        # 기존 항목 제거
        self.clear_items()
        
        # 모듈 관리 버튼 추가
        module_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="모듈 관리",
            emoji="🧩"
        )
        module_button.callback = self.module_button_callback
        self.add_item(module_button)
        
        # 게임 설정 버튼 추가 - 최대 2-3개만 표시하고 나머지는 다른 UI로 분리
        game_keys = list(self.bot_config.game_settings.keys())
        for i, game in enumerate(game_keys[:3]):  # 처음 3개만 표시
            game_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=f"{game} 설정",
                emoji="🎮",
                row=1
            )
            # 클로저 문제 해결을 위한 함수 생성
            game_button.callback = lambda interaction, game_name=game: self.game_button_callback(interaction, game_name)
            self.add_item(game_button)
        
        # 게임 설정이 더 있으면 추가 버튼
        if len(game_keys) > 3:
            more_games_button = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label="더 많은 게임 설정",
                emoji="🎲",
                row=1
            )
            more_games_button.callback = self.more_games_button_callback
            self.add_item(more_games_button)
        
        # 날씨 설정 버튼 추가
        weather_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="날씨 시스템 설정",
            emoji="🌤️",
            row=2
        )
        weather_button.callback = self.weather_button_callback
        self.add_item(weather_button)
        
        # 로깅 설정 버튼 추가
        logging_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="로깅 설정",
            emoji="📋",
            row=2
        )
        logging_button.callback = self.logging_button_callback
        self.add_item(logging_button)
        
        # 관리자 설정 버튼 추가
        admin_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label="관리자 설정",
            emoji="👑",
            row=2
        )
        admin_button.callback = self.admin_button_callback
        self.add_item(admin_button)
        
        # 디버그 정보 버튼 추가
        debug_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="디버그 정보",
            emoji="🔍",
            row=3
        )
        debug_button.callback = self.debug_button_callback
        self.add_item(debug_button)
    
    async def module_button_callback(self, interaction: discord.Interaction):
        """모듈 관리 버튼 콜백"""
        # 모듈 뷰에서 처리
        from .module_views import handle_module_select
        await handle_module_select(interaction, self.bot, self.bot_config, self)
    
    async def game_button_callback(self, interaction: discord.Interaction, game_name: str):
        """게임 설정 버튼 콜백"""
        # 게임 설정 뷰에서 처리
        # 게임별로 다른 모듈 호출
        if game_name == "judgment":
            from .game_settings.judgment import handle_judgment_settings
            await handle_judgment_settings(interaction, self.bot, self.bot_config)
        elif game_name == "mine":
            from .game_settings.mine import handle_mine_settings
            await handle_mine_settings(interaction, self.bot, self.bot_config)
        elif game_name == "blackjack":
            from .game_settings.blackjack import handle_blackjack_settings
            await handle_blackjack_settings(interaction, self.bot, self.bot_config)
        else:
            # 기본 게임 설정 핸들러
            from .game_settings.generic import handle_game_settings
            await handle_game_settings(interaction, self.bot, self.bot_config, game_name)
    
    async def more_games_button_callback(self, interaction: discord.Interaction):
        """더 많은 게임 설정 버튼 콜백"""
        # 관리자 권한 확인
        if str(interaction.user.id) not in self.bot_config.admin_ids:
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return
        
        # 게임 목록 표시 UI
        embed = discord.Embed(
            title="🎮 게임 설정",
            description="설정할 게임을 선택하세요.",
            color=discord.Color.green()
        )
        
        # 게임 선택 드롭다운
        view = discord.ui.View(timeout=300)
        options = [
            discord.SelectOption(label=game, value=game)
            for game in self.bot_config.game_settings.keys()
        ]
        
        select = discord.ui.Select(
            placeholder="게임 선택...",
            options=options
        )
        
        async def select_callback(select_interaction):
            game_name = select.values[0]
            await self.game_button_callback(select_interaction, game_name)
        
        select.callback = select_callback
        view.add_item(select)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    async def weather_button_callback(self, interaction: discord.Interaction):
        """날씨 설정 버튼 콜백"""
        # 날씨 설정 뷰에서 처리
        from .weather_settings import handle_weather_settings
        await handle_weather_settings(interaction, self.bot, self.bot_config)
    
    async def logging_button_callback(self, interaction: discord.Interaction):
        """로깅 설정 버튼 콜백"""
        # 로깅 설정 뷰에서 처리
        from .logging_settings import handle_logging_settings
        await handle_logging_settings(interaction, self.bot, self.bot_config)
    
    async def admin_button_callback(self, interaction: discord.Interaction):
        """관리자 설정 버튼 콜백"""
        # 관리자 설정 뷰에서 처리
        from .admin_settings import handle_admin_settings
        await handle_admin_settings(interaction, self.bot, self.bot_config)
    
    async def debug_button_callback(self, interaction: discord.Interaction):
        """디버그 정보 버튼 콜백"""
        # 관리자 권한 확인
        if str(interaction.user.id) not in self.bot_config.admin_ids:
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return
        
        # 디버그 매니저에서 상태 임베드 가져오기
        embed = debug_manager.create_debug_embed()
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def refresh_message(self):
        """제어판 메시지 새로고침"""
        if not self.message:
            return
        
        # 제어판 임베드 생성
        embed = create_control_panel_embed(self.bot, self.bot_config)
        
        # 메시지 업데이트
        await self.message.edit(embed=embed, view=self)

# 제어판 생성 함수
def create_control_panel_embed(bot, bot_config):
    """제어판 임베드 생성"""
    embed = discord.Embed(
        title="⚙️ 봇 제어판",
        description="버튼을 클릭하여 다양한 설정을 관리하세요.",
        color=discord.Color.blue()
    )
    
    # 모듈 상태
    modules_status = []
    for module, state in bot_config.modules.items():
        loaded = bot_config.modules_loaded.get(module, False)
        status = f"✅ 활성화{' (로드됨)' if loaded else ''}" if state else "❌ 비활성화"
        modules_status.append(f"`{module}`: {status}")
    
    embed.add_field(name="모듈 상태", value="\n".join(modules_status), inline=False)
    
    # 디버그 상태
    from utils.logger import DEBUG_MODE, VERBOSE_DEBUG
    debug_status = []
    debug_status.append(f"디버그 모드: {'✅ 활성화' if DEBUG_MODE else '❌ 비활성화'}")
    debug_status.append(f"상세 디버그: {'✅ 활성화' if VERBOSE_DEBUG else '❌ 비활성화'}")
    
    embed.add_field(name="디버그 상태", value="\n".join(debug_status), inline=True)
    
    # 현재 날씨 정보
    weather_cog = bot.get_cog('WeatherCommands')
    if weather_cog and hasattr(weather_cog, 'weather_system'):
        weather = weather_cog.weather_system.current_weather['global']['weather']
        embed.add_field(name="현재 날씨", value=f"🌤️ {weather}", inline=True)
    
    # 마지막 업데이트 시간
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    embed.set_footer(text=f"마지막 업데이트: {now}")
    
    return embed

# 제어판 명령어 처리 함수
async def handle_control_panel_command(bot, message, bot_config):
    """제어판 명령어 처리"""
    author_id = str(message.author.id)
    
    log_info(f"[on_message] 제어판 명령어 감지됨: {message.author.name}({author_id})")
    
    # 관리자 권한 확인 
    if author_id not in bot_config.admin_ids:
        log_info(f"[on_message] 권한 거부: {message.author.name}은(는) 관리자가 아님")
        await message.channel.send("⛔ 이 명령어는 관리자만 사용할 수 있습니다.", delete_after=5)
        return
        
    log_info(f"[on_message] 제어판 생성 시작: {message.author.name}")
    
    log_info(f"제어판 요청: {message.author.name} ({message.author.id})")
    
    # 제어판 임베드 생성
    embed = create_control_panel_embed(bot, bot_config)
    
    # 제어판 뷰 생성
    view = ControlPanelView(bot, bot_config)
    panel_message = await message.channel.send(embed=embed, view=view)
    view.message = panel_message

# 모듈 초기화 함수
def setup_control_panel(bot, bot_config):
    """제어판 설정"""
    log_info("제어판 설정 완료")
    
    # 모듈 뷰 초기화
    from .module_views import setup_module_views
    setup_module_views(bot, bot_config)
    
    # 게임 설정 초기화
    from .game_settings import setup_game_settings
    setup_game_settings(bot, bot_config)
    
    # 날씨 설정 초기화
    from .weather_settings import setup_weather_settings
    setup_weather_settings(bot, bot_config)
    
    # 로깅 설정 초기화
    from .logging_settings import setup_logging_settings
    setup_logging_settings(bot, bot_config)
    
    # 관리자 설정 초기화
    from .admin_settings import setup_admin_settings
    setup_admin_settings(bot, bot_config)