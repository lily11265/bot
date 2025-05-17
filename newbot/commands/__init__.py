# commands/__init__.py

"""
봇 명령어 및 이벤트 핸들링 모듈입니다.
- 관리자 명령어
- 이벤트 핸들러
"""

from .event_handlers import setup_event_handlers
from .admin_commands import register_admin_commands

__all__ = [
    'setup_event_handlers',
    'register_admin_commands'
]

def setup_commands(bot, bot_config):
    """명령어 설정"""
    from utils.logger import log_info
    
    # 이벤트 핸들러 설정
    setup_event_handlers(bot, bot_config)
    
    # 관리자 명령어 등록
    register_admin_commands(bot, bot_config)
    
    log_info("봇 명령어 설정 완료")