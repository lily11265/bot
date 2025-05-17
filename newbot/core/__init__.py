# core/__init__.py

"""
봇의 핵심 기능을 관리하는 모듈입니다.
- BotConfig: 봇 설정 관리
- ModuleLoader: 모듈 로딩 및 핫 리로딩
- EventManager: 이벤트 처리 및 관리
"""

# 주요 클래스 가져오기
from .bot_config import BotConfig, koreanize_setting_name
from .module_loader import ModuleLoader
from .event_manager import EventManager

__all__ = [
    'BotConfig',
    'koreanize_setting_name',
    'ModuleLoader',
    'EventManager'
]