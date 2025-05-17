# core/bot_config.py
import os
import json
from typing import Dict, Any, Optional, List

from utils.logger import log_debug, log_info, log_warning, log_error

class BotConfig:
    """봇 설정 관리 클래스"""
    
    def __init__(self, config_file: str = 'bot_config.json'):
        self.config_file = config_file
        
        # 모든 모듈을 포함하도록 수정
        self.modules = {
            # 기본 모듈
            "utility": True,
            "weather": True,
            "quest": True,
            "affection": True,
            "judgment": True,  # 판정 모듈 추가

            # 게임 모듈
            "gambling" : True,
            "poker_game" : True,
            "horse_racing" : True,
            "roulette" : True,
            "dice_poker" : True,
            "blackjack": True,
            "ladder_game": True, 
            "mine": True,
            "forest": True,
            "fishing": True,
            "combat_update": True,
            "farming": True,
            "shop": True,
            "shop_system": True,
            "effect": True,
            "hunting": True,
            "tavern": True,
            
            # 기타 기능 모듈
            "diary": True,
            "wireless_manager": True,
            "reaction_trigger": True,
            "quest_commands": True,
            "phone": True,
            "judgment_ephemeral": True
        }
        
        # 모듈 활성화 상태
        self.modules_loaded = {module: False for module in self.modules}
        
        # 미니게임 설정
        self.game_settings = {
            # 판정 설정
            "judgment": {
                "debug_mode": False,           # 디버그 모드
                "great_failure_threshold": 10, # 대실패 기준값
                "failure_threshold":49,       # 실패 기준값
                "success_threshold": 90,       # 성공 기준값
                "margin_threshold": 3,         # 경계선 차이 기준값
                "enable_ephemeral_messages": True,  # Ephemeral 메시지 기능 활성화
                "ephemeral_cooldown": 900,     # Ephemeral 메시지 쿨다운 (초)
                "spreadsheet_id": ""           # Google 스프레드시트 ID
            },
            "blackjack": {
                "debug_mode": False,
                "dealer_bust_chance": 0.3,    # 딜러 버스트 확률
                "dealer_low_card_chance": 0.4 # 딜러 낮은 카드 확률
            },
            # 기타 게임 설정 (원본 코드와 동일)
        }
        
        # 날씨 시스템 설정
        self.weather_settings = {
            "enable_weather_system": True,           # 날씨 시스템 활성화
            "enable_channel_specific_weather": False, # 채널별 날씨 활성화
            "horror_mode_probability": 5.0,          # 공포모드 확률(%)
            "unique_item_probability": 5.0,          # 유니크 아이템 확률(%)
            "notify_weather_changes": True           # 날씨 변경 알림
        }

        # 로깅 설정
        self.logging = {
            "debug_mode": True,            # 전체 디버그 모드
            "verbose_debug": True,         # 매우 상세한 디버그
            "log_commands": True,          # 명령어 로깅
            "log_to_file": True,           # 파일 로깅
            "discord_channel_log": True,   # 디스코드 채널 로깅
            "debug_channel_id": None       # 디버그 채널 ID
        }
        
        # 관리자 ID 목록
        self.admin_ids = ["1007172975222603798", "1090546247770832910"]
        
        # 변경된 설정 추적 (보고용)
        self.changed_settings = {}
        
        # 기타 설정
        self.enable_hot_reload = True     # 핫 리로딩 활성화 여부
    
    def load(self) -> bool:
        """설정 파일에서 설정 로드"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 설정 업데이트
                if 'modules' in data:
                    # 기존 모듈에만 상태 업데이트
                    for module, state in data['modules'].items():
                        if module in self.modules:
                            self.modules[module] = state
                
                if 'game_settings' in data:
                    # 중첩 딕셔너리 업데이트 (깊은 병합)
                    self._update_nested_dict(self.game_settings, data['game_settings'])
                
                if 'weather_settings' in data:
                    self.weather_settings.update(data['weather_settings'])
                
                if 'logging' in data:
                    self.logging.update(data['logging'])
                
                if 'admin_ids' in data:
                    self.admin_ids = data['admin_ids']
                
                if 'enable_hot_reload' in data:
                    self.enable_hot_reload = data['enable_hot_reload']
                
                log_info(f"설정을 '{self.config_file}'에서 로드했습니다.")
                return True
            else:
                log_info(f"'{self.config_file}'이 존재하지 않습니다. 기본 설정을 사용합니다.")
                # 기본 설정 저장
                self.save()
                return False
        except Exception as e:
            log_error(f"설정 로드 중 오류 발생: {e}", e)
            return False
    
    def save(self) -> bool:
        """설정을 파일에 저장"""
        try:
            data = {
                'modules': self.modules,
                'game_settings': self.game_settings,
                'weather_settings': self.weather_settings,
                'logging': self.logging,
                'admin_ids': self.admin_ids,
                'enable_hot_reload': self.enable_hot_reload
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            log_info(f"설정을 '{self.config_file}'에 저장했습니다.")
            return True
        except Exception as e:
            log_error(f"설정 저장 중 오류 발생: {e}", e)
            return False
    
    def track_change(self, category: str, key: str, old_value: Any, new_value: Any, subkey: Optional[str] = None) -> None:
        """설정 변경 사항 추적"""
        if category not in self.changed_settings:
            self.changed_settings[category] = {}
        
        if subkey:
            # 중첩 설정 (예: game_settings.blackjack.debug_mode)
            if key not in self.changed_settings[category]:
                self.changed_settings[category][key] = {}
            self.changed_settings[category][key][subkey] = {
                "old": old_value,
                "new": new_value
            }
        else:
            # 일반 설정 (예: modules.blackjack)
            self.changed_settings[category][key] = {
                "old": old_value,
                "new": new_value
            }
    
    def clear_changes(self) -> None:
        """변경 내역 초기화"""
        self.changed_settings = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """설정 값 가져오기"""
        # 점 표기법 지원 (예: "logging.debug_mode")
        if '.' in key:
            parts = key.split('.')
            value = self.__dict__
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
            return value
        
        # 일반 키 조회
        return self.__dict__.get(key, default)
    
    def set(self, key: str, value: Any) -> bool:
        """설정 값 설정"""
        try:
            # 점 표기법 지원 (예: "logging.debug_mode")
            if '.' in key:
                parts = key.split('.')
                target = self.__dict__
                for i, part in enumerate(parts[:-1]):
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                
                # 변경 추적
                if parts[-1] in target:
                    old_value = target[parts[-1]]
                    self.track_change(parts[0], parts[-1], old_value, value)
                
                target[parts[-1]] = value
            else:
                # 일반 키 설정
                if key in self.__dict__:
                    old_value = self.__dict__[key]
                    self.track_change("root", key, old_value, value)
                
                self.__dict__[key] = value
            
            return True
        except Exception as e:
            log_error(f"설정 값 설정 중 오류 발생: {e}", e)
            return False
    
    def _update_nested_dict(self, original: Dict, updates: Dict) -> Dict:
        """중첩 딕셔너리 업데이트 (깊은 병합)"""
        for key, value in updates.items():
            if isinstance(value, dict) and key in original and isinstance(original[key], dict):
                self._update_nested_dict(original[key], value)
            else:
                original[key] = value
        return original

def koreanize_setting_name(name):
    """설정 이름을 한국어로 변환"""
    translations = {
        "Debug Mode": "디버그 모드",
        "Dealer Bust Chance": "딜러 버스트 확률",
        "Dealer Low Card Chance": "딜러 낮은 카드 확률",
        "Cooldown": "쿨타임",
        "Memory Time": "기억 시간",
        "Card Display Time": "카드 표시 시간",
        "Base Fishing Time": "기본 낚시 시간",
        "Animation Time": "애니메이션 시간",
        "Answer Time": "응답 시간",
        "Enable Item Loss": "아이템 손실 활성화",
        "Min Item Loss": "최소 아이템 손실",
        "Max Item Loss": "최대 아이템 손실",
        "Max Bullets": "최대 총알 수",
        "Hunt Duration": "사냥 지속 시간",
        "Cafe Cooldown": "카페 쿨타임",
        "Drink Cooldown": "음료 쿨타임",
        "Effect Duration": "효과 지속 시간",
        "Drunk Duration": "취함 지속 시간",
        "Great Success Threshold": "대성공 기준",
        "Success Threshold": "성공 기준",
        "Great Failure Threshold": "대실패 기준",
        "Enable Hp Recovery": "체력 회복 활성화",
        "Enable Item Reward": "아이템 보상 활성화",
        "Enable Perfect Bonus": "완벽 보너스 활성화"
    }
    
    return translations.get(name, name)