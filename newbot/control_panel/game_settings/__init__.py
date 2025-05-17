# control_panel/game_settings/__init__.py

"""
게임 설정 관련 모듈입니다.
- 일반 게임 설정 관리
- 특수 게임별 설정 관리 (블랙잭, 채굴, 판정 등)
"""

from utils.logger import log_debug, log_info

def setup_game_settings(bot, bot_config):
    """게임 설정 초기화"""
    log_debug("게임 설정 모듈 초기화 중...")
    
    # 게임별 설정 초기화
    try:
        # 마인 설정 초기화
        from .mine import handle_mine_settings
        log_debug("채굴 설정 모듈 초기화됨")
        
        # 판정 설정 초기화
        from .judgment import handle_judgment_settings 
        log_debug("판정 설정 모듈 초기화됨")
        
        # 블랙잭 설정 초기화
        from .blackjack import handle_blackjack_settings
        log_debug("블랙잭 설정 모듈 초기화됨")
        
        # 기본 설정 초기화
        from .generic import handle_game_settings
        log_debug("일반 게임 설정 모듈 초기화됨")
    except Exception as e:
        from utils.logger import log_error
        log_error(f"게임 설정 초기화 중 오류 발생: {e}", e)
    
    log_info("게임 설정 모듈 초기화 완료")

__all__ = [
    'setup_game_settings',
    'handle_game_settings',
    'ModuleBasicSettingsModal',
    'ModuleAdditionalSettingsModal'
]

# 일반 게임 설정 핸들러 가져오기
from .generic import handle_game_settings, ModuleBasicSettingsModal, ModuleAdditionalSettingsModal