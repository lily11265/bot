import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio
import os
import sys
import traceback
from typing import Optional, List

from utils.logger import log_debug, log_info, log_warning, log_error
from debug_manager import debug_manager

class AdminCommands(commands.Cog):
    """관리자용 명령어"""
    
    def __init__(self, bot, bot_config):
        self.bot = bot
        self.bot_config = bot_config
    
    async def is_admin(self, user_id):
        """사용자가 관리자인지 확인"""
        return str(user_id) in self.bot_config.admin_ids
    
    async def cog_check(self, ctx):
        """모든 명령어에 대한 기본 체크 - 관리자만 사용 가능"""
        return await self.is_admin(ctx.author.id)
    
    @commands.command(name="reload")
    async def reload_module(self, ctx, module_name: str):
        """특정 모듈 리로드 (관리자만 사용 가능)"""
        if not await self.is_admin(ctx.author.id):
            return await ctx.send("⛔ 권한이 없습니다.")
            
        # 모듈 리로드
        from core.module_loader import ModuleLoader
        module_loader = ModuleLoader(self.bot, self.bot_config)
        
        log_info(f"모듈 리로드 요청: {module_name} (요청자: {ctx.author.name})")
        
        if module_name not in self.bot_config.modules:
            await ctx.send(f"⚠️ 모듈 '{module_name}'을(를) 찾을 수 없습니다.")
            return
        
        # 모듈 리로드 진행
        success, message = await module_loader.reload_module(module_name)
        
        if success:
            await ctx.send(f"✅ 모듈 '{module_name}'을(를) 성공적으로 리로드했습니다.")
        else:
            await ctx.send(f"❌ 모듈 리로드 실패: {message}")
    
    @commands.command(name="reloadall")
    async def reload_all_modules(self, ctx):
        """모든 모듈 리로드 (관리자만 사용 가능)"""
        if not await self.is_admin(ctx.author.id):
            return await ctx.send("⛔ 권한이 없습니다.")
            
        # 모듈 리로더 생성
        from core.module_loader import ModuleLoader
        module_loader = ModuleLoader(self.bot, self.bot_config)
        
        log_info(f"모든 모듈 리로드 요청 (요청자: {ctx.author.name})")
        
        # 로딩 메시지
        message = await ctx.send("🔄 모든 모듈 리로드 중...")
        
        # 모든 활성화된 모듈 리로드
        success_count = 0
        fail_count = 0
        failed_modules = []
        
        for module_name, state in self.bot_config.modules.items():
            if state and self.bot_config.modules_loaded.get(module_name, False):
                await message.edit(content=f"🔄 모듈 '{module_name}' 리로드 중...")
                success, result = await module_loader.reload_module(module_name)
                
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                    failed_modules.append(module_name)
        
        # 결과 메시지
        if fail_count == 0:
            await message.edit(content=f"✅ 모든 모듈이 성공적으로 리로드되었습니다. (총 {success_count}개)")
        else:
            result_message = f"⚠️ 모듈 리로드 완료: 성공 {success_count}개, 실패 {fail_count}개\n"
            result_message += f"실패한 모듈: {', '.join(failed_modules)}"
            await message.edit(content=result_message)

    # 슬래시 명령어로 변경 - 관리자 전용 + 다른 사람에게 표시 안 함
    @app_commands.command(name="debug", description="디버그 설정 변경")
    async def debug_command(self, interaction: discord.Interaction, mode: str, value: str):
        """디버그 설정 변경 (슬래시 명령어)"""
        # 관리자 권한 확인
        if not await self.is_admin(interaction.user.id):
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return
        
        # 디버그 설정 변경
        if mode == "mode":
            # 디버그 모드 설정
            debug_mode = value.lower() in ["on", "true", "1", "yes", "y"]
            
            # 설정 업데이트
            from utils.logger import setup_logger, VERBOSE_DEBUG
            setup_logger(
                self.bot_config.logging.get("log_file", "bot_log.log"),
                debug_mode,
                VERBOSE_DEBUG,
                self.bot_config.logging.get("log_to_file", True)
            )
            
            # 디버그 매니저 설정 업데이트
            debug_manager.toggle_debug_mode(debug_mode)
            
            # 설정 저장
            self.bot_config.logging["debug_mode"] = debug_mode
            self.bot_config.save()
            
            log_info(f"디버그 모드 변경: {debug_mode} (요청자: {interaction.user.name})")
            await interaction.response.send_message(f"✅ 디버그 모드가 {'활성화' if debug_mode else '비활성화'}되었습니다.")
        
        elif mode == "verbose":
            # 상세 디버그 설정
            verbose_debug = value.lower() in ["on", "true", "1", "yes", "y"]
            
            # 설정 업데이트
            from utils.logger import setup_logger, DEBUG_MODE
            setup_logger(
                self.bot_config.logging.get("log_file", "bot_log.log"),
                DEBUG_MODE,
                verbose_debug,
                self.bot_config.logging.get("log_to_file", True)
            )
            
            # 디버그 매니저 설정 업데이트
            debug_manager.toggle_verbose_debug(verbose_debug)
            
            # 설정 저장
            self.bot_config.logging["verbose_debug"] = verbose_debug
            self.bot_config.save()
            
            log_info(f"상세 디버그 모드 변경: {verbose_debug} (요청자: {interaction.user.name})")
            await interaction.response.send_message(f"✅ 상세 디버그 모드가 {'활성화' if verbose_debug else '비활성화'}되었습니다.")
        
        elif mode == "channel":
            # 디버그 채널 설정
            if value.lower() == "here":
                # 현재 채널을 디버그 채널로 설정
                channel_id = interaction.channel.id
                channel = interaction.channel
            else:
                # 채널 ID 파싱
                try:
                    channel_id = int(value.strip())
                    channel = self.bot.get_channel(channel_id)
                    if not channel:
                        await interaction.response.send_message(f"⚠️ 채널 ID {channel_id}를 찾을 수 없습니다.", ephemeral=True)
                        return
                except ValueError:
                    await interaction.response.send_message("⚠️ 유효한 채널 ID 또는 'here'를 입력하세요.", ephemeral=True)
                    return
            
            # 디버그 채널 설정
            from utils.logger import set_debug_channel
            set_debug_channel(channel)
            
            # 설정 저장
            self.bot_config.logging["debug_channel_id"] = channel_id
            self.bot_config.save()
            
            log_info(f"디버그 채널 설정: #{channel.name} (ID: {channel_id}) (요청자: {interaction.user.name})")
            await interaction.response.send_message(f"✅ 디버그 채널이 #{channel.name}(으)로 설정되었습니다.")
            
            # 디버그 채널에 알림
            await channel.send("🔍 이 채널이 디버그 로그 채널로 설정되었습니다.")
        
        else:
            # 알 수 없는 모드
            await interaction.response.send_message(f"⚠️ 알 수 없는 모드: {mode}. 사용 가능한 모드: mode, verbose, channel", ephemeral=True)
    
    @app_commands.command(name="hotreload", description="핫 리로딩 설정 변경")
    async def hot_reload_command(self, interaction: discord.Interaction, enabled: bool):
        """핫 리로딩 설정 변경 (슬래시 명령어)"""
        # 관리자 권한 확인
        if not await self.is_admin(interaction.user.id):
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return
        
        # 설정 업데이트
        self.bot_config.enable_hot_reload = enabled
        self.bot_config.save()
        
        log_info(f"핫 리로딩 설정 변경: {enabled} (요청자: {interaction.user.name})")
        await interaction.response.send_message(f"✅ 핫 리로딩이 {'활성화' if enabled else '비활성화'}되었습니다.")
        
        # 핫 리로딩 태스크 재시작이 필요한 경우
        if enabled:
            await interaction.followup.send("🔄 다음 봇 재시작 시 핫 리로딩이 활성화됩니다.")

# commands/admin_commands.py - register_admin_commands 함수 수정

def register_admin_commands(bot, bot_config):
    """관리자 명령어 등록"""
    # 기존 cog 등록
    cog = AdminCommands(bot, bot_config)
    bot.add_cog(cog)
    
    # 기존 명령어 제거 후 다시 추가 (동기화 문제 해결)
    for cmd in bot.tree.get_commands():
        if cmd.name in ['debug', 'hotreload']:
            bot.tree.remove_command(cmd.name)
    
    # 명령어 등록 디버그 로그 추가
    log_debug(f"등록 전 명령어 목록: {[cmd.name for cmd in bot.tree.get_commands()]}", verbose=True)
    
    # 명령어를 다시 등록
    @bot.tree.command(name="debug", description="디버그 설정 변경")
    @app_commands.describe(
        mode="설정할 모드 (mode/verbose/channel)",
        value="설정할 값"
    )
    async def debug_command(interaction: discord.Interaction, mode: str, value: str):
        """디버그 설정 변경 (슬래시 명령어)"""
        # 관리자 권한 확인
        if str(interaction.user.id) not in bot_config.admin_ids:
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return
        
        # 디버그 설정 변경
        if mode == "mode":
            # 디버그 모드 설정
            debug_mode = value.lower() in ["on", "true", "1", "yes", "y"]
            
            # 설정 업데이트
            from utils.logger import setup_logger, VERBOSE_DEBUG
            setup_logger(
                bot_config.logging.get("log_file", "bot_log.log"),
                debug_mode,
                VERBOSE_DEBUG,
                bot_config.logging.get("log_to_file", True)
            )
            
            # 디버그 매니저 설정 업데이트
            debug_manager.toggle_debug_mode(debug_mode)
            
            # 설정 저장
            bot_config.logging["debug_mode"] = debug_mode
            bot_config.save()
            
            log_info(f"디버그 모드 변경: {debug_mode} (요청자: {interaction.user.name})")
            await interaction.response.send_message(f"✅ 디버그 모드가 {'활성화' if debug_mode else '비활성화'}되었습니다.")
        
        elif mode == "verbose":
            # 상세 디버그 설정
            verbose_debug = value.lower() in ["on", "true", "1", "yes", "y"]
            
            # 설정 업데이트
            from utils.logger import setup_logger, DEBUG_MODE
            setup_logger(
                bot_config.logging.get("log_file", "bot_log.log"),
                DEBUG_MODE,
                verbose_debug,
                bot_config.logging.get("log_to_file", True)
            )
            
            # 디버그 매니저 설정 업데이트
            debug_manager.toggle_verbose_debug(verbose_debug)
            
            # 설정 저장
            bot_config.logging["verbose_debug"] = verbose_debug
            bot_config.save()
            
            log_info(f"상세 디버그 모드 변경: {verbose_debug} (요청자: {interaction.user.name})")
            await interaction.response.send_message(f"✅ 상세 디버그 모드가 {'활성화' if verbose_debug else '비활성화'}되었습니다.")
        
        elif mode == "channel":
            # 디버그 채널 설정
            if value.lower() == "here":
                # 현재 채널을 디버그 채널로 설정
                channel_id = interaction.channel.id
                channel = interaction.channel
            else:
                # 채널 ID 파싱
                try:
                    channel_id = int(value.strip())
                    channel = bot.get_channel(channel_id)
                    if not channel:
                        await interaction.response.send_message(f"⚠️ 채널 ID {channel_id}를 찾을 수 없습니다.", ephemeral=True)
                        return
                except ValueError:
                    await interaction.response.send_message("⚠️ 유효한 채널 ID 또는 'here'를 입력하세요.", ephemeral=True)
                    return
            
            # 디버그 채널 설정
            from utils.logger import set_debug_channel
            set_debug_channel(channel)
            
            # 설정 저장
            bot_config.logging["debug_channel_id"] = channel_id
            bot_config.save()
            
            log_info(f"디버그 채널 설정: #{channel.name} (ID: {channel_id}) (요청자: {interaction.user.name})")
            await interaction.response.send_message(f"✅ 디버그 채널이 #{channel.name}(으)로 설정되었습니다.")
            
            # 디버그 채널에 알림
            await channel.send("🔍 이 채널이 디버그 로그 채널로 설정되었습니다.")
        
        else:
            # 알 수 없는 모드
            await interaction.response.send_message(f"⚠️ 알 수 없는 모드: {mode}. 사용 가능한 모드: mode, verbose, channel", ephemeral=True)

    @bot.tree.command(name="hotreload", description="핫 리로딩 설정 변경")
    @app_commands.describe(
        enabled="핫 리로딩 활성화 여부"
    )
    async def hot_reload_command(interaction: discord.Interaction, enabled: bool):
        """핫 리로딩 설정 변경 (슬래시 명령어)"""
        # 관리자 권한 확인
        if str(interaction.user.id) not in bot_config.admin_ids:
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return
        
        # 설정 업데이트
        bot_config.enable_hot_reload = enabled
        bot_config.save()
        
        log_info(f"핫 리로딩 설정 변경: {enabled} (요청자: {interaction.user.name})")
        await interaction.response.send_message(f"✅ 핫 리로딩이 {'활성화' if enabled else '비활성화'}되었습니다.")
        
        # 핫 리로딩 태스크 재시작이 필요한 경우
        if enabled:
            await interaction.followup.send("🔄 다음 봇 재시작 시 핫 리로딩이 활성화됩니다.")
    
    # 등록 후 명령어 목록 확인
    log_debug(f"등록 후 명령어 목록: {[cmd.name for cmd in bot.tree.get_commands()]}", verbose=True)
    log_info("관리자 명령어 등록 완료")
    
    log_info("관리자 명령어 등록 완료")