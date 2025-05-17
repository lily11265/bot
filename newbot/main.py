# main.py - 중앙 관리자 & 진입점
import discord
from discord.ext import commands
import asyncio
import os
import sys
import logging
import platform
import traceback
from dotenv import load_dotenv
import time
import datetime

# 유틸리티 모듈 임포트
from utils.logger import setup_logger, log_debug, log_info, log_warning, log_error
from utils.helpers import safe_int_convert, safe_float_convert

# 핵심 모듈 임포트
from core.bot_config import BotConfig
from core.module_loader import ModuleLoader
from core.event_manager import EventManager

# 디버그 매니저 임포트
from debug_manager import debug_manager

# 환경 변수 로드
load_dotenv()

# 설정 파일 경로
CONFIG_FILE = 'bot_config.json'
LOG_FILE = 'bot_log.log'

# 봇 설정 초기화
bot_config = BotConfig(CONFIG_FILE)
bot_config.load()

# 전역 디버그 설정
GLOBAL_DEBUG_MODE = True  # 디버그 모드 켜기/끄기
GLOBAL_VERBOSE_DEBUG = True  # 상세 디버그 켜기/끄기 
GLOBAL_LOG_TO_FILE = True  # 파일 로깅 켜기/끄기
# 로거 설정
DEBUG_MODE = bot_config.logging.get("debug_mode", True)
VERBOSE_DEBUG = bot_config.logging.get("verbose_debug", True)
LOG_TO_FILE = bot_config.logging.get("log_to_file", True)
setup_logger(LOG_FILE, DEBUG_MODE, VERBOSE_DEBUG, LOG_TO_FILE)

# 봇 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 봇 인스턴스 생성
bot = commands.Bot(command_prefix='/', intents=intents)

# 모듈 로더 초기화
module_loader = ModuleLoader(bot, bot_config)

# 이벤트 매니저 초기화
event_manager = EventManager(bot, bot_config)

# 핫 리로딩 기능
async def hot_reload_task():
    """모듈 파일 변경 감지하여 핫 리로딩"""
    if not bot_config.get("enable_hot_reload", False):
        return
    
    while True:
        try:
            # 30초마다 모듈 변경 확인
            await asyncio.sleep(30)
            
            # 모듈 변경 확인
            changed_modules = await module_loader.check_for_module_changes()
            
            # 변경된 모듈이 있으면 리로드
            for module_name in changed_modules:
                log_info(f"모듈 변경 감지: {module_name} - 자동 리로드 중...")
                success, message = await module_loader.reload_module(module_name)
                
                if success:
                    log_info(f"모듈 {module_name} 핫 리로드 성공")
                    
                    # 디버그 채널에 알림
                    from utils.logger import get_debug_channel
                    debug_channel = get_debug_channel()
                    if debug_channel:
                        await debug_channel.send(f"🔄 모듈 `{module_name}` 변경 감지 - 자동 리로드 완료")
                else:
                    log_error(f"모듈 {module_name} 핫 리로드 실패: {message}")
        except Exception as e:
            log_error(f"핫 리로딩 작업 중 오류 발생: {e}", e)
            await asyncio.sleep(60)  # 오류 발생 시 더 오래 대기

# main.py 파일에서 on_ready 이벤트 수정
@bot.event
async def on_ready():
    """봇이 준비되었을 때 초기화"""
    log_info(f'봇이 로그인되었습니다: {bot.user.name} (ID: {bot.user.id})')
    log_info(f'Discord.py 버전: {discord.__version__}')
    log_info(f'Python 버전: {platform.python_version()}')
    log_info(f'실행 환경: {platform.system()} {platform.release()}')
    log_info('------')
    
    # 설정 디버그 채널 초기화
    debug_channel_id = bot_config.logging.get("debug_channel_id")
    if debug_channel_id:
        channel = bot.get_channel(int(debug_channel_id))
        if channel:
            from utils.logger import set_debug_channel
            set_debug_channel(channel)
            await channel.send("🟢 봇이 시작되었습니다.")
            log_info(f"디버그 채널 설정됨: #{channel.name}")
        else:
            log_warning(f"디버그 채널을 찾을 수 없습니다: {debug_channel_id}")
    
    # 모듈 로딩
    await module_loader.load_all_modules()
    
    # 모듈 설정 적용
    module_loader.apply_module_settings()
    
    # 명령어 설정 - 이 부분 추가
    from commands import setup_commands
    setup_commands(bot, bot_config)
    
    # 제어판 설정
    from control_panel.panel_manager import setup_control_panel
    setup_control_panel(bot, bot_config)
    
    # 이벤트 핸들러 설정
    event_manager.setup_event_handlers()
    
    # 명령어 동기화
    try:
        log_info("슬래시 명령어 동기화 중...")
        # 명령어 동기화 전 목록 확인
        before_commands = [cmd.name for cmd in bot.tree.get_commands()]
        log_debug(f"동기화 전 명령어 목록: {before_commands}", verbose=True)
        
        # 관리자 명령어 재등록 강제
        from commands import register_admin_commands
        register_admin_commands(bot, bot_config)
        
        # 명령어 동기화
        synced = await bot.tree.sync()
        log_info(f"슬래시 명령어 {len(synced)}개 동기화 완료")
        
        # 동기화 후 명령어 목록 확인
        after_commands = [cmd.name for cmd in synced]
        log_debug(f"동기화 후 명령어 목록: {after_commands}", verbose=True)
        
        # 관리자 명령어 디버그 로그
        admin_ids = bot_config.admin_ids
        log_debug(f"현재 등록된 관리자 ID: {admin_ids}", verbose=True)
    except Exception as e:
        log_error(f"명령어 동기화 중 오류 발생: {e}", e)
    
    log_info("봇 초기화 완료")

# 메시지 이벤트 처리
@bot.event
async def on_message(message):
    # 봇 메시지 무시
    if message.author.bot:
        return
    
    # 명령어 처리는 이벤트 매니저에게 위임
    await event_manager.process_commands(message)
    
    # 기본 명령어 처리
    await bot.process_commands(message)

# 애플리케이션 명령어 오류 처리
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    await event_manager.handle_app_command_error(interaction, error)

# 봇 실행
def main():
    """봇 메인 함수 - 초기화 및 실행"""
    log_debug("메인 함수 시작: 초기화 및 실행 준비", verbose=True)
    
    # 시스템 환경 체크
    log_debug(f"시스템 환경 체크: OS={platform.system()}, 버전={platform.release()}, Python={platform.python_version()}", verbose=True)
    log_debug(f"실행 경로: {os.getcwd()}", verbose=True)
    
    # 환경 변수 체크
    log_debug("환경 변수 확인 시작", verbose=True)
    env_vars = {k: "***" if "TOKEN" in k else v for k, v in os.environ.items() if k.startswith("DISCORD")}
    log_debug(f"디스코드 관련 환경 변수: {env_vars}", verbose=True)
    
    # 토큰 가져오기
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        log_warning("환경 변수에서 DISCORD_TOKEN을 찾을 수 없습니다. .env 파일을 확인하세요.")
        TOKEN = ''  # 기본값 - 실제 토큰으로 교체 필요
    
    log_debug(f"토큰 형식 확인: 길이={len(TOKEN)}, 시작={TOKEN[:5]}...", verbose=True)
    
    try:
        # 봇 실행 (핫 리로딩 태스크는 on_ready에서 시작)
        log_debug("bot.run() 호출로 메인 이벤트 루프 시작", verbose=True)
        log_info(f"Discord 봇 실행 - 플랫폼: {platform.system()} {platform.release()}")
        bot.run(TOKEN)
    except discord.errors.LoginFailure as e:
        log_debug(f"로그인 실패: {type(e).__name__}", verbose=True)
        log_error(f"봇 로그인 실패: 토큰이 유효하지 않습니다. {e}")
    except discord.errors.HTTPException as e:
        log_debug(f"HTTP 오류: 상태 코드 {e.status}, {e.text}", verbose=True)
        log_error(f"봇 시작 중 HTTP 오류 발생: {e}")
    except Exception as e:
        tb_text = traceback.format_exc()
        log_debug(f"예외 타입: {type(e).__name__}", verbose=True)
        log_debug(f"예외 발생 위치:\n{tb_text}", verbose=True)
        log_error(f"봇 시작 중 오류 발생: {e}", e)
    finally:
        log_debug("main() 함수 종료", verbose=True)

if __name__ == "__main__":
    main()