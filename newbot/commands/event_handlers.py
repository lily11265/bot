# commands/event_handlers.py
import discord
from discord.ext import commands
import datetime
import os
import re
import traceback
from typing import Dict, List, Tuple, Any, Optional

from utils.logger import log_debug, log_info, log_warning, log_error
from debug_manager import debug_manager

def setup_event_handlers(bot, bot_config):
    """이벤트 핸들러 설정"""
    log_info("이벤트 핸들러 설정 중...")
    
    # 이벤트 핸들러 설정
    @bot.event
    async def on_error(event, *args, **kwargs):
        """봇 오류 이벤트 처리"""
        error = traceback.format_exc()
        log_error(f"이벤트 {event} 처리 중 오류 발생: {error}")
        
        # 디버그 채널로 오류 보고
        await debug_manager.send_error_to_channel(bot, f"이벤트 {event} 처리 중 오류 발생", Exception(error))
    
    @bot.event
    async def on_command_error(ctx, error):
        """명령어 오류 이벤트 처리"""
        if isinstance(error, commands.CommandNotFound):
            # 명령어를 찾을 수 없음 (무시)
            return
        elif isinstance(error, commands.MissingPermissions):
            await ctx.send("이 명령어를 사용할 권한이 없습니다.")
        elif isinstance(error, commands.NotOwner):
            await ctx.send("이 명령어는 봇 오너만 사용할 수 있습니다.")
        else:
            # 기타 오류
            log_error(f"명령어 {ctx.command} 실행 중 오류 발생: {error}", error)
            
            # 디버그 채널로 오류 보고
            await debug_manager.send_error_to_channel(bot, f"명령어 {ctx.command} 실행 중 오류 발생", error)
            
            # 사용자에게 알림
            await ctx.send(f"명령어 실행 중 오류가 발생했습니다: {error}")
    
    @bot.event
    async def on_connect():
        """봇 연결 이벤트"""
        log_info(f"Discord 서버에 연결되었습니다.")
    
    @bot.event
    async def on_disconnect():
        """봇 연결 해제 이벤트"""
        log_warning(f"Discord 서버와 연결이 끊어졌습니다.")
    
    @bot.event
    async def on_resumed():
        """봇 세션 재개 이벤트"""
        log_info(f"Discord 세션이 재개되었습니다.")
    
    @bot.event
    async def on_guild_join(guild):
        """길드 입장 이벤트"""
        log_info(f"새로운 서버에 참여했습니다: {guild.name} (ID: {guild.id})")
        
        # 디버그 채널에 알림
        await debug_manager.send_error_to_channel(
            bot, 
            f"새로운 서버에 참여했습니다: {guild.name} (ID: {guild.id})",
            None
        )
    
    @bot.event
    async def on_guild_remove(guild):
        """길드 퇴장 이벤트"""
        log_info(f"서버에서 퇴장했습니다: {guild.name} (ID: {guild.id})")
        
        # 디버그 채널에 알림
        await debug_manager.send_error_to_channel(
            bot, 
            f"서버에서 퇴장했습니다: {guild.name} (ID: {guild.id})",
            None
        )
    
    @bot.event
    async def on_message(message):
        """메시지 이벤트 처리"""
        # 봇 메시지 무시
        if message.author.bot:
            return
        
        # 명령어 처리는 EventManager에게 위임
        from core.event_manager import EventManager
        event_manager = EventManager(bot, bot_config)
        await event_manager.process_commands(message)
        
        # 기본 명령어 처리
        await bot.process_commands(message)
    
    log_info("이벤트 핸들러 설정 완료")