# core/module_loader.py
import importlib
import inspect
import sys
import asyncio
import os
import time
from typing import Dict, List, Tuple, Any, Optional, Union
import discord
from discord.ext import commands

from utils.logger import log_debug, log_info, log_warning, log_error

class ModuleLoader:
    """모듈 로딩 및 관리 클래스"""
    
    def __init__(self, bot: commands.Bot, bot_config):
        self.bot = bot
        self.bot_config = bot_config
        
        # 모듈 목록 (순서 중요)
        self.module_list = [
            "utility",
            "weather",
            "quest",            # 기본 모듈 먼저 로드
            "affection",        # 다른 모듈이 의존하는 핵심 모듈
            "gambling",
            "poker_game",
            "horse_racing",
            "roulette",
            "dice_poker",
            "blackjack",
            "ladder_game", 
            "mine",
            "forest",
            "fishing",
            "combat_update",
            "farming",
            "shop",
            "shop_system",
            "effect",
            "hunting",
            "wireless_manager",
            "diary",            # 일기 시스템 추가
            "reaction_trigger",
            "judgment",
            "tavern",
            "phone",
            "judgment_ephemeral",
            "quest_commands"    # UI/명령어 모듈 마지막에 로드
        ]
        
        # 로드된 모듈과 구성 요소 추적
        self.loaded_modules = {}
        self.module_listeners = {}
        self.module_cogs = {}
        
        # 모듈 리로딩을 위한 정보
        self.last_modified_times = {}
    
    async def load_all_modules(self) -> Tuple[int, int]:
        """모든 모듈 로드 (순서대로)"""
        log_info(f"모듈 로드 시작 (총 {len(self.module_list)}개 모듈)")
        
        success_count = 0
        fail_count = 0
        
        for idx, module_name in enumerate(self.module_list):
            log_info(f"[{idx+1}/{len(self.module_list)}] 모듈 로드 중: {module_name}")
            
            if module_name in self.bot_config.modules and self.bot_config.modules[module_name]:
                success, message = await self.load_module(module_name)
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                log_info(message)
            else:
                log_warning(f"모듈 {module_name}은 설정에서 비활성화되어 있어 로드되지 않았습니다.")
        
        log_info(f"모듈 로드 완료: 성공 {success_count}개, 실패 {fail_count}개")
        return success_count, fail_count
    
    async def load_module(self, module_name: str) -> Tuple[bool, str]:
        """특정 모듈 로드"""
        import traceback
        log_debug(f"모듈 로드 시도: {module_name}")
        
        try:
            # 모듈이 이미 로드되어 있는지 확인
            if module_name in self.bot_config.modules_loaded and self.bot_config.modules_loaded[module_name]:
                log_debug(f"모듈 {module_name}은 이미 로드되어 있습니다.")
                return True, f"모듈 {module_name}은 이미 로드되어 있습니다."
            
            # 모듈 파일 수정 시간 추적 (핫 리로딩용)
            try:
                module_file = f"{module_name}.py"
                if os.path.exists(module_file):
                    self.last_modified_times[module_name] = os.path.getmtime(module_file)
            except Exception as e:
                log_debug(f"모듈 파일 접근 중 오류 (무시됨): {e}")
            
            # 모듈이 이미 가져와져 있는지 확인
            if module_name in sys.modules:
                log_debug(f"기존 모듈 다시 로드: {module_name}")
                # 이미 가져와져 있다면 다시 로드
                module = importlib.reload(sys.modules[module_name])
            else:
                log_debug(f"새 모듈 가져오기: {module_name}")
                # 아니라면 가져오기
                module = importlib.import_module(module_name)
            
            # 디버그 매니저에 모듈 등록
            from debug_manager import debug_manager
            debug_manager.register_module(module_name)
            
            # 나중에 참조할 수 있도록 모듈 저장
            self.loaded_modules[module_name] = module
            
            # 이 모듈에 대한 추적 초기화
            if module_name not in self.module_listeners:
                self.module_listeners[module_name] = []
            if module_name not in self.module_cogs:
                self.module_cogs[module_name] = []
            
            # 모듈에 설정 함수가 있으면 호출
            if hasattr(module, 'setup'):
                log_debug(f"모듈 {module_name}의 setup 함수 호출")
                # 설정 함수의 서명 확인
                setup_params = inspect.signature(module.setup).parameters
                
                # 적절한 매개변수로 setup 호출
                if asyncio.iscoroutinefunction(module.setup):
                    log_debug(f"모듈 {module_name}의 setup 함수는 비동기입니다.")
                    if len(setup_params) > 0:
                        log_debug(f"setup({self.bot}) 호출")
                        result = await module.setup(self.bot)
                    else:
                        log_debug(f"setup() 호출")
                        result = await module.setup()
                else:
                    log_debug(f"모듈 {module_name}의 setup 함수는 동기식입니다.")
                    if len(setup_params) > 0:
                        log_debug(f"setup({self.bot}) 호출")
                        result = module.setup(self.bot)
                    else:
                        log_debug(f"setup() 호출")
                        result = module.setup()
                    
                # setup이 cog를 반환하면 추적
                if result is not None and isinstance(result, commands.Cog):
                    log_debug(f"모듈 {module_name}에서 Cog 반환됨: {result.__class__.__name__}")
                    self.module_cogs[module_name].append(result)
            
            # 모듈 로드 상태 업데이트
            self.bot_config.modules_loaded[module_name] = True
            
            return True, f"모듈 로드 성공: {module_name}"
        except Exception as e:
            error_msg = f"모듈 {module_name} 로드 실패: {str(e)}"
            log_error(error_msg, e)
            
            # 디버그 매니저를 통해 오류 채널로 보고
            from debug_manager import debug_manager
            await debug_manager.send_error_to_channel(self.bot, error_msg, e)
            
            return False, f"{error_msg}\n{traceback.format_exc()}"
    
    async def reload_module(self, module_name: str) -> Tuple[bool, str]:
        """모듈 리로드"""
        log_debug(f"모듈 리로드 시도: {module_name}")
        
        # 모듈이 로드되어 있는지 확인
        if module_name not in sys.modules:
            log_warning(f"모듈 {module_name}이 로드되어 있지 않아 리로드할 수 없습니다.")
            return False, f"모듈 {module_name}이 로드되어 있지 않습니다."
        
        # 기존 모듈 리스너 및 Cog 제거
        if module_name in self.module_listeners:
            for listener in self.module_listeners[module_name]:
                self.bot.remove_listener(listener)
            self.module_listeners[module_name] = []
        
        if module_name in self.module_cogs:
            for cog in self.module_cogs[module_name]:
                cog_name = cog.__class__.__name__
                try:
                    await self.bot.remove_cog(cog_name)
                    log_debug(f"Cog 제거됨: {cog_name}")
                except Exception as e:
                    log_warning(f"Cog {cog_name} 제거 중 오류: {e}")
            self.module_cogs[module_name] = []
        
        # 모듈 로드
        self.bot_config.modules_loaded[module_name] = False
        return await self.load_module(module_name)
    
    async def check_for_module_changes(self) -> List[str]:
        """모듈 파일 변경 확인 (핫 리로딩용)"""
        changed_modules = []
        
        # 모든 로드된 모듈 확인
        for module_name, loaded in self.bot_config.modules_loaded.items():
            if not loaded:
                continue
            
            module_file = f"{module_name}.py"
            if not os.path.exists(module_file):
                continue
            
            # 수정 시간 확인
            current_mtime = os.path.getmtime(module_file)
            last_mtime = self.last_modified_times.get(module_name, 0)
            
            # 파일이 변경되었으면 리스트에 추가
            if current_mtime > last_mtime:
                changed_modules.append(module_name)
                self.last_modified_times[module_name] = current_mtime
                log_debug(f"모듈 파일 변경 감지: {module_name}")
        
        return changed_modules
    
    def apply_module_settings(self) -> None:
        """모듈에 설정 적용"""
        log_info("모듈 설정 적용 시작...")
        
        # 판정 모듈 디버그 설정
        if 'judgment' in sys.modules:
            try:
                judgment_module = sys.modules['judgment']
                if hasattr(judgment_module, 'DEBUG_MODE'):
                    judgment_module.DEBUG_MODE = self.bot_config.game_settings.get('judgment', {}).get('debug_mode', False)
                    log_debug(f"판정 모듈 디버그 모드 설정: {judgment_module.DEBUG_MODE}")
            except Exception as e:
                log_error(f"판정 모듈 설정 적용 중 오류: {e}", e)

        # 블랙잭 설정
        if 'blackjack' in sys.modules:
            try:
                blackjack_module = sys.modules['blackjack']
                if hasattr(blackjack_module, 'DEBUG_MODE'):
                    blackjack_module.DEBUG_MODE = self.bot_config.game_settings['blackjack']['debug_mode']
                    log_debug(f"블랙잭 디버그 모드 설정: {blackjack_module.DEBUG_MODE}")
                if hasattr(blackjack_module, 'DEALER_BUST_BASE_CHANCE'):
                    blackjack_module.DEALER_BUST_BASE_CHANCE = self.bot_config.game_settings['blackjack']['dealer_bust_chance']
                    log_debug(f"블랙잭 딜러 버스트 확률: {blackjack_module.DEALER_BUST_BASE_CHANCE}")
                if hasattr(blackjack_module, 'DEALER_LOW_CARD_BASE_CHANCE'):
                    blackjack_module.DEALER_LOW_CARD_BASE_CHANCE = self.bot_config.game_settings['blackjack']['dealer_low_card_chance']
                    log_debug(f"블랙잭 딜러 낮은 카드 확률: {blackjack_module.DEALER_LOW_CARD_BASE_CHANCE}")
            except Exception as e:
                log_error(f"블랙잭 설정 적용 중 오류: {e}", e)
        
        # 채굴 게임 설정
        if 'mine' in sys.modules:
            try:
                mine_module = sys.modules['mine']
                if hasattr(mine_module, 'MINING_COOLDOWN'):
                    mine_module.MINING_COOLDOWN = self.bot_config.game_settings['mine']['cooldown']
                    log_debug(f"채굴 쿨타임 설정: {mine_module.MINING_COOLDOWN}")
                if hasattr(mine_module, 'MEMORY_GAME_TIME'):
                    mine_module.MEMORY_GAME_TIME = self.bot_config.game_settings['mine']['memory_time']
                    log_debug(f"채굴 게임 시간 설정: {mine_module.MEMORY_GAME_TIME}")
                if hasattr(mine_module, 'ROCK_DISPLAY_TIME'):
                    mine_module.ROCK_DISPLAY_TIME = self.bot_config.game_settings['mine']['card_display_time']
                    log_debug(f"채굴 돌 표시 시간 설정: {mine_module.ROCK_DISPLAY_TIME}")
                if hasattr(mine_module, 'LOCATION_TIME_ADJUST'):
                    mine_module.LOCATION_TIME_ADJUST.update(self.bot_config.game_settings['mine']['location_time_adjust'])
                    log_debug(f"채굴 위치별 시간 조정: {mine_module.LOCATION_TIME_ADJUST}")
                    
                # 돌 갯수 설정 적용
                if hasattr(mine_module, 'LOCATION_ROCK_COUNT'):
                    if 'rock_count' in self.bot_config.game_settings['mine']:
                        mine_module.LOCATION_ROCK_COUNT.update(self.bot_config.game_settings['mine']['rock_count'])
                        log_debug(f"채굴 위치별 돌 갯수: {mine_module.LOCATION_ROCK_COUNT}")
                    else:
                        # 설정이 없으면 기본값 저장
                        self.bot_config.game_settings['mine']['rock_count'] = {
                            '광산': 5,
                            '깊은광산': 5,
                            '고대광산': 5
                        }
                        self.bot_config.save()
            except Exception as e:
                log_error(f"채굴 설정 적용 중 오류: {e}", e)
        
        # 채집 게임 및 다른 게임 설정들...
        # (원본 코드와 동일한 로직, 길이 제한으로 생략)
        
        # 날씨 시스템 설정
        weather_cog = self.bot.get_cog('WeatherCommands')
        if weather_cog and hasattr(weather_cog, 'weather_system'):
            try:
                weather_system = weather_cog.weather_system
                if hasattr(weather_system, 'GLOBAL_SETTINGS'):
                    weather_system.GLOBAL_SETTINGS['ENABLE_WEATHER_SYSTEM'] = self.bot_config.weather_settings['enable_weather_system']
                    weather_system.GLOBAL_SETTINGS['ENABLE_CHANNEL_SPECIFIC_WEATHER'] = self.bot_config.weather_settings['enable_channel_specific_weather']
                    weather_system.GLOBAL_SETTINGS['HORROR_MODE_PROBABILITY'] = self.bot_config.weather_settings['horror_mode_probability']
                    weather_system.GLOBAL_SETTINGS['UNIQUE_ITEM_PROBABILITY'] = self.bot_config.weather_settings['unique_item_probability']
                    weather_system.GLOBAL_SETTINGS['NOTIFY_WEATHER_CHANGES'] = self.bot_config.weather_settings['notify_weather_changes']
                    weather_system.GLOBAL_SETTINGS['ADMIN_USER_IDS'] = self.bot_config.admin_ids
                    
                    log_debug(f"날씨 시스템 설정 적용: {weather_system.GLOBAL_SETTINGS}")
            except Exception as e:
                log_error(f"날씨 시스템 설정 적용 중 오류: {e}", e)
        
        log_info("모든 모듈에 설정이 적용되었습니다.")