# control_panel/__init__.py

"""
봇 제어판 관련 기능을 관리하는 모듈입니다.
- 모듈 관리
- 게임 설정 관리
- 날씨 설정 관리
- 로깅 설정 관리
- 관리자 설정 관리
"""

# 제어판 메인 함수 가져오기
from .panel_manager import setup_control_panel, handle_control_panel_command

__all__ = [
    'setup_control_panel',
    'handle_control_panel_command'
]

# 봇 인스턴스 저장 변수
_bot = None
_bot_config = None

def init(bot, bot_config):
    """제어판 모듈 초기화"""
    global _bot, _bot_config
    _bot = bot
    _bot_config = bot_config
    
    # 하위 모듈 초기화
    from .module_views import setup_module_views
    setup_module_views(bot, bot_config)
    
    from .game_settings import setup_game_settings
    setup_game_settings(bot, bot_config)
    
    from .weather_settings import setup_weather_settings
    setup_weather_settings(bot, bot_config)
    
    from .logging_settings import setup_logging_settings
    setup_logging_settings(bot, bot_config)
    
    from .admin_settings import setup_admin_settings
    setup_admin_settings(bot, bot_config)
    
    from utils.logger import log_info
    log_info("제어판 모듈 초기화 완료")