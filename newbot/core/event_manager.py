# core/event_manager.py
import discord
from discord.ext import commands
import datetime
import os
import re
import traceback
from typing import Dict, List, Tuple, Any, Optional

from utils.logger import log_debug, log_info, log_warning, log_error
from debug_manager import debug_manager

class EventManager:
    """이벤트 관리 클래스"""
    
    def __init__(self, bot: commands.Bot, bot_config):
        self.bot = bot
        self.bot_config = bot_config
    
    def setup_event_handlers(self) -> None:
        """이벤트 핸들러 설정"""
        log_info("이벤트 핸들러 설정 중...")
        
        # 이벤트 핸들러 설정
        @self.bot.event
        async def on_error(event, *args, **kwargs):
            """봇 오류 이벤트 처리"""
            error = traceback.format_exc()
            log_error(f"이벤트 {event} 처리 중 오류 발생: {error}")
            
            # 디버그 채널로 오류 보고
            await debug_manager.send_error_to_channel(self.bot, f"이벤트 {event} 처리 중 오류 발생", Exception(error))
        
        @self.bot.event
        async def on_command_error(ctx, error):
            """명령어 오류 이벤트 처리"""
            if isinstance(error, commands.CommandNotFound):
                # 명령어를 찾을 수 없음 (무시)
                return
            elif isinstance(error, commands.MissingPermissions):
                await ctx.send("이 명령어를 사용할 권한이 없습니다.")
            else:
                # 기타 오류
                log_error(f"명령어 {ctx.command} 실행 중 오류 발생: {error}", error)
                
                # 디버그 채널로 오류 보고
                await debug_manager.send_error_to_channel(self.bot, f"명령어 {ctx.command} 실행 중 오류 발생", error)
                
                # 사용자에게 알림
                await ctx.send(f"명령어 실행 중 오류가 발생했습니다: {error}")
        
        @self.bot.event
        async def on_connect():
            """봇 연결 이벤트"""
            log_info(f"Discord 서버에 연결되었습니다.")
        
        @self.bot.event
        async def on_disconnect():
            """봇 연결 해제 이벤트"""
            log_warning(f"Discord 서버와 연결이 끊어졌습니다.")
        
        @self.bot.event
        async def on_resumed():
            """봇 세션 재개 이벤트"""
            log_info(f"Discord 세션이 재개되었습니다.")
        
        log_info("이벤트 핸들러 설정 완료")
    
    async def process_commands(self, message: discord.Message) -> None:
        """명령어 처리"""
        content = message.content.strip()
        author_id = str(message.author.id)
        
        log_info(f"[on_message] 메시지 수신: {message.author.name}({author_id}): '{content}'")
        
        # !제어판 명령어 처리 - 이 부분은 control_panel.panel_manager에서 처리하게 됨
        if content == "!제어판":
            # 제어판 컴포넌트에서 처리
            from control_panel.panel_manager import handle_control_panel_command
            await handle_control_panel_command(self.bot, message, self.bot_config)
        
        # !디버그 명령어 처리
        elif message.content.startswith("!디버그"):
            # 관리자 권한 확인
            if str(message.author.id) not in self.bot_config.admin_ids:
                await message.channel.send("⛔ 이 명령어는 관리자만 사용할 수 있습니다.", delete_after=5)
                return
            
            # 디버그 명령어 로직
            await self._handle_debug_command(message)
    
    async def _handle_debug_command(self, message: discord.Message) -> None:
        """디버그 명령어 처리"""
        # 글로벌 변수 미리 선언
        from utils.logger import DEBUG_MODE, VERBOSE_DEBUG, setup_logger
        
        args = message.content.split()
        if len(args) > 1:
            command = args[1].lower()
            
            # 디버그 모드 토글
            if command in ["on", "off"]:
                debug_mode = (command == "on")
                
                # utility.py 설정 업데이트
                setup_logger(self.bot_config.logging.get("log_file", "bot_log.log"), 
                            debug_mode, 
                            VERBOSE_DEBUG, 
                            self.bot_config.logging.get("log_to_file", True))
                
                # 디버그 매니저 설정 업데이트
                debug_manager.toggle_debug_mode(debug_mode)
                
                # 설정 저장
                self.bot_config.logging["debug_mode"] = debug_mode
                self.bot_config.save()
                
                log_info(f"디버그 모드 변경: {debug_mode}")
                await message.channel.send(f"✅ 디버그 모드가 {'활성화' if debug_mode else '비활성화'}되었습니다.")
            
            # 상세 디버그 모드 토글
            elif command in ["verbose", "normal"]:
                verbose_debug = (command == "verbose")
                
                # utility.py 설정 업데이트
                setup_logger(self.bot_config.logging.get("log_file", "bot_log.log"), 
                            DEBUG_MODE, 
                            verbose_debug, 
                            self.bot_config.logging.get("log_to_file", True))
                
                # 디버그 매니저 설정 업데이트
                debug_manager.toggle_verbose_debug(verbose_debug)
                
                # 설정 저장
                self.bot_config.logging["verbose_debug"] = verbose_debug
                self.bot_config.save()
                
                log_info(f"상세 디버그 모드 변경: {verbose_debug}")
                await message.channel.send(f"✅ 상세 디버그 모드가 {'활성화' if verbose_debug else '비활성화'}되었습니다.")
            
            # 디버그 상태 확인
            elif command == "status":
                status = f"디버그 모드: {'활성화' if DEBUG_MODE else '비활성화'}\n"
                status += f"상세 디버그: {'활성화' if VERBOSE_DEBUG else '비활성화'}"
                
                await message.channel.send(f"```\n{status}\n```")
            
            # 모듈 정보 출력
            elif command == "modules":
                modules_info = "로드된 모듈 목록:\n"
                for module, state in self.bot_config.modules_loaded.items():
                    modules_info += f"- {module}: {'✅' if state else '❌'}\n"
                
                await message.channel.send(f"```\n{modules_info}\n```")
            
            # 디버그 매니저 정보 출력
            elif command == "manager":
                embed = debug_manager.create_debug_embed()
                await message.channel.send(embed=embed)
            
            # 시스템 정보 출력
            elif command == "system":
                import platform
                system_info = f"Python 버전: {platform.python_version()}\n"
                system_info += f"Discord.py 버전: {discord.__version__}\n"
                system_info += f"운영체제: {platform.system()} {platform.release()}\n"
                system_info += f"디버그 모드: {'활성화' if DEBUG_MODE else '비활성화'}\n"
                system_info += f"상세 디버그: {'활성화' if VERBOSE_DEBUG else '비활성화'}\n"
                
                await message.channel.send(f"```\n{system_info}\n```")
            
            else:
                await message.channel.send("⚠️ 알 수 없는 디버그 명령어입니다. 사용 가능한 명령어: on, off, verbose, normal, status, modules, manager, system")
        else:
            # 사용법 안내
            usage = "디버그 명령어 사용법:\n"
            usage += "!디버그 on - 디버그 모드 켜기\n"
            usage += "!디버그 off - 디버그 모드 끄기\n"
            usage += "!디버그 verbose - 상세 디버그 켜기\n"
            usage += "!디버그 normal - 상세 디버그 끄기\n"
            usage += "!디버그 status - 디버그 상태 확인\n"
            usage += "!디버그 modules - 모듈 상태 확인\n"
            usage += "!디버그 manager - 디버그 매니저 정보\n"
            usage += "!디버그 system - 시스템 정보 확인"
            
            await message.channel.send(f"```\n{usage}\n```")
    
    async def handle_app_command_error(self, interaction: discord.Interaction, 
                                       error: discord.app_commands.AppCommandError) -> None:
        """애플리케이션 명령어 오류 처리"""
        if isinstance(error, discord.app_commands.errors.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        else:
            # 오류 로그
            log_error(f"명령어 {interaction.command.name if interaction.command else 'unknown'}에서 오류 발생: {error}", error)
            
            # 디버그 매니저를 통해 오류 채널로 보고
            await debug_manager.send_error_to_channel(self.bot, f"명령어 {interaction.command.name if interaction.command else 'unknown'}에서 오류 발생", error)
            
            # 사용자에게 알림
            error_message = f"명령어 실행 중 오류가 발생했습니다: {error}"
            if interaction.response.is_done():
                await interaction.followup.send(error_message, ephemeral=True)
            else:
                await interaction.response.send_message(error_message, ephemeral=True)