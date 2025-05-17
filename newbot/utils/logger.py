# utils/logger.py
import logging
import traceback
import discord
import datetime
import os
import asyncio
from typing import Optional, Dict, Any, List

# 디버그 모드 설정 (전역 변수)
DEBUG_MODE = True
VERBOSE_DEBUG = True

# 로거 인스턴스
logger = logging.getLogger('discord_bot')

# 디버그 채널 인스턴스 (디스코드 채널 로깅용)
_debug_channel = None

def setup_logger(log_file: str = 'bot_log.log', debug_mode: bool = True, verbose: bool = True, log_to_file: bool = True) -> None:
    """
    로깅 설정 초기화
    
    Args:
        log_file (str): 로그 파일 경로
        debug_mode (bool): 디버그 모드 여부
        verbose (bool): 상세 로깅 여부
        log_to_file (bool): 파일 로깅 여부
    """
    global DEBUG_MODE, VERBOSE_DEBUG, logger
    DEBUG_MODE = debug_mode
    VERBOSE_DEBUG = verbose
    
    # 로거 레벨 설정
    logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # 이미 핸들러가 있는지 확인
    if logger.handlers:
        # 기존 핸들러의 로깅 레벨 업데이트
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        return
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    logger.addHandler(console_handler)
    
    # 파일 로깅
    if log_to_file:
        # 로그 디렉토리 확인
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 파일 핸들러
        file_handler = logging.FileHandler(filename=log_file, encoding='utf-8', mode='a')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        logger.addHandler(file_handler)
    
    logger.info(f"로깅 설정 완료: 디버그={debug_mode}, 상세={verbose}, 파일로깅={log_to_file}")

def set_debug_channel(channel: discord.TextChannel) -> None:
    """디버그 채널 설정"""
    global _debug_channel
    _debug_channel = channel
    logger.info(f"디버그 채널 설정됨: #{channel.name}")

def get_debug_channel() -> Optional[discord.TextChannel]:
    """디버그 채널 가져오기"""
    return _debug_channel

def log_debug(message: str, verbose: bool = False) -> None:
    """
    디버그 로그 출력 함수
    
    Args:
        message (str): 로그 메시지
        verbose (bool): 상세 로그 여부
    """
    if DEBUG_MODE:
        if not verbose or (verbose and VERBOSE_DEBUG):
            logger.debug(message)
            
            # 디스코드 채널 로깅
            if _debug_channel:
                asyncio.create_task(_log_to_discord(message, 'debug'))

def log_info(message: str) -> None:
    """정보 로그 출력 함수"""
    logger.info(message)
    
    # 디스코드 채널 로깅
    if _debug_channel:
        asyncio.create_task(_log_to_discord(message, 'info'))

def log_warning(message: str) -> None:
    """경고 로그 출력 함수"""
    logger.warning(message)
    
    # 디스코드 채널 로깅
    if _debug_channel:
        asyncio.create_task(_log_to_discord(message, 'warning'))

def log_error(message: str, exc_info: Optional[Exception] = None) -> None:
    """
    에러 로그 출력 함수
    
    Args:
        message (str): 에러 메시지
        exc_info (Exception, optional): 예외 정보
    """
    if exc_info:
        logger.error(message, exc_info=True)
    else:
        logger.error(message)
    
    # 디스코드 채널 로깅
    if _debug_channel:
        asyncio.create_task(_log_to_discord(message, 'error', exc_info))

async def _log_to_discord(message: str, level: str, exc_info: Optional[Exception] = None) -> None:
    """디스코드 채널에 로그 출력"""
    if not _debug_channel:
        return
    
    # 로그 수준에 따른 색상 및 이모지
    colors = {
        'debug': discord.Color.light_gray(),
        'info': discord.Color.blue(),
        'warning': discord.Color.gold(),
        'error': discord.Color.red()
    }
    
    emojis = {
        'debug': '🔍',
        'info': 'ℹ️',
        'warning': '⚠️',
        'error': '❌'
    }
    
    # 로그 임베드 생성
    embed = discord.Embed(
        title=f"{emojis.get(level, '📝')} {level.upper()}",
        description=message[:2000],  # 설명 필드 2000자 제한
        color=colors.get(level, discord.Color.default()),
        timestamp=datetime.datetime.now()
    )
    
    # 예외 정보 추가
    if exc_info:
        tb = traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)
        tb_text = ''.join(tb)
        
        # 오류 정보가 너무 길면 잘라냄
        if len(tb_text) > 1000:
            tb_text = tb_text[:997] + "..."
        
        embed.add_field(name="예외 정보", value=f"```py\n{tb_text}\n```", inline=False)
    
    try:
        await _debug_channel.send(embed=embed)
    except Exception as e:
        # 디스코드 채널에 메시지 전송 실패 시 콘솔에만 출력
        logger.error(f"디스코드 채널에 로그 전송 중 오류 발생: {e}")