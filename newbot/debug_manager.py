import logging
import os
import datetime
import discord
from typing import Dict, Any, List, Optional
from utility import log_debug, log_info, log_warning, log_error, save_json, load_json
import traceback

class DebugManager:
    """
    디버그 관리 클래스
    """
    def __init__(self, config_file: str = 'debug_config.json'):
        self.config_file = config_file
        
        # 설정 기본값
        self.settings = {
            "debug_mode": True,            # 전체 디버그 모드
            "verbose_debug": True,         # 매우 상세한 디버그
            "log_commands": True,          # 명령어 로깅
            "log_to_file": True,           # 파일 로깅
            "log_file": "bot_log.log",     # 로그 파일 경로
            "log_rotation": True,          # 로그 파일 로테이션
            "max_log_files": 10,           # 최대 로그 파일 수
            "max_log_size_mb": 10,         # 최대 로그 파일 크기 (MB)
            "module_debugging": {},        # 모듈별 디버그 설정
            "error_channel_id": None       # 오류 보고 채널 ID
        }
        
        # 로거 인스턴스 - 이미 존재하는 로거 사용
        self.logger = logging.getLogger('discord_bot')
        
        # 활성화된 모듈 목록
        self.active_modules = set()
        
        # 로그 파일 핸들러
        self.file_handler = None
        
        # 설정 로드
        self.load_settings()
        
        # 로거 초기화 - 중복 체크 포함
        self.setup_logger()
    
    def load_settings(self) -> None:
        """설정 로드"""
        config = load_json(self.config_file, self.settings)
        self.settings.update(config)
        log_info(f"디버그 설정 로드됨: {self.config_file}")
    
    def save_settings(self) -> None:
        """설정 저장"""
        save_json(self.config_file, self.settings)
        log_info(f"디버그 설정 저장됨: {self.config_file}")
    
    def setup_logger(self) -> None:
        """로거 설정"""
        # 로거 레벨 설정
        self.logger.setLevel(logging.DEBUG if self.settings["debug_mode"] else logging.INFO)
        
        # 기존 핸들러가 있는지 확인
        existing_handlers = len(self.logger.handlers) > 0
        
        # 이미 핸들러가 설정되어 있으면 새로 추가하지 않고 설정만 업데이트
        if existing_handlers:
            log_debug("DebugManager: 기존 로거 핸들러가 발견되어 설정만 업데이트합니다.", False)
            return
        
        # 기존 핸들러 제거
        if self.file_handler and self.file_handler in self.logger.handlers:
            self.logger.removeHandler(self.file_handler)
            self.file_handler = None
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
        
        # 핸들러 초기화
        self.logger.handlers = [console_handler]
        
        # 파일 로깅
        if self.settings["log_to_file"]:
            # 로그 파일 로테이션
            if self.settings["log_rotation"]:
                from logging.handlers import RotatingFileHandler
                
                # 파일 크기 (바이트 단위로 변환)
                max_bytes = self.settings["max_log_size_mb"] * 1024 * 1024
                
                self.file_handler = RotatingFileHandler(
                    filename=self.settings["log_file"],
                    encoding='utf-8',
                    maxBytes=max_bytes,
                    backupCount=self.settings["max_log_files"]
                )
            else:
                # 일반 파일 핸들러
                self.file_handler = logging.FileHandler(
                    filename=self.settings["log_file"],
                    encoding='utf-8',
                    mode='a'
                )
            
            # 포맷터 설정
            self.file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            
            # 핸들러 추가
            self.logger.addHandler(self.file_handler)
        
        log_info(f"DebugManager: 로거 설정 완료: 디버그={self.settings['debug_mode']}, " + 
                f"상세={self.settings['verbose_debug']}, " + 
                f"파일로깅={self.settings['log_to_file']}")
    
    def toggle_debug_mode(self, debug_mode: bool) -> None:
        """
        디버그 모드 토글
        
        Args:
            debug_mode (bool): 디버그 모드 활성화 여부
        """
        self.settings["debug_mode"] = debug_mode
        self.logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
        self.save_settings()
        log_info(f"디버그 모드 변경: {debug_mode}")
    
    def toggle_verbose_debug(self, verbose: bool) -> None:
        """
        상세 디버그 토글
        
        Args:
            verbose (bool): 상세 디버그 활성화 여부
        """
        self.settings["verbose_debug"] = verbose
        self.save_settings()
        log_info(f"상세 디버그 모드 변경: {verbose}")
    
    def set_module_debug(self, module_name: str, enabled: bool) -> None:
        """
        모듈별 디버그 설정
        
        Args:
            module_name (str): 모듈 이름
            enabled (bool): 디버그 활성화 여부
        """
        self.settings["module_debugging"][module_name] = enabled
        self.save_settings()
        log_info(f"모듈 {module_name} 디버그 설정: {enabled}")
    
    def is_module_debug_enabled(self, module_name: str) -> bool:
        """
        모듈 디버그 활성화 여부 확인
        
        Args:
            module_name (str): 모듈 이름
            
        Returns:
            bool: 디버그 활성화 여부
        """
        # 전체 디버그 모드가 꺼져있으면 항상 False
        if not self.settings["debug_mode"]:
            return False
        
        # 모듈별 설정이 있으면 그 설정 사용
        if module_name in self.settings["module_debugging"]:
            return self.settings["module_debugging"][module_name]
        
        # 기본적으로 활성화
        return True
    
    def register_module(self, module_name: str) -> None:
        """
        모듈 등록
        
        Args:
            module_name (str): 모듈 이름
        """
        self.active_modules.add(module_name)
        
        # 모듈별 디버그 설정이 없으면 기본값 추가
        if module_name not in self.settings["module_debugging"]:
            self.settings["module_debugging"][module_name] = True
            self.save_settings()
        
        log_debug(f"모듈 등록됨: {module_name}", False)
    
    def unregister_module(self, module_name: str) -> None:
        """
        모듈 등록 해제
        
        Args:
            module_name (str): 모듈 이름
        """
        if module_name in self.active_modules:
            self.active_modules.remove(module_name)
            log_debug(f"모듈 등록 해제됨: {module_name}", False)
    
    def log_debug(self, message: str, module: str = None, verbose: bool = False) -> None:
        """
        디버그 로그 출력
        
        Args:
            message (str): 로그 메시지
            module (str, optional): 모듈 이름
            verbose (bool, optional): 상세 로그 여부
        """
        # 모듈이 지정된 경우 모듈별 디버그 설정 확인
        if module and not self.is_module_debug_enabled(module):
            return
        
        # 상세 로그 여부 확인
        if verbose and not self.settings["verbose_debug"]:
            return
        
        # 모듈 접두사 추가
        if module:
            message = f"[{module}] {message}"
        
        # 로그 출력
        self.logger.debug(message)
    
    def log_info(self, message: str, module: str = None) -> None:
        """
        정보 로그 출력
        
        Args:
            message (str): 로그 메시지
            module (str, optional): 모듈 이름
        """
        if module:
            message = f"[{module}] {message}"
        
        self.logger.info(message)
    
    def log_warning(self, message: str, module: str = None) -> None:
        """
        경고 로그 출력
        
        Args:
            message (str): 로그 메시지
            module (str, optional): 모듈 이름
        """
        if module:
            message = f"[{module}] {message}"
        
        self.logger.warning(message)
    
    def log_error(self, message: str, exc_info: Optional[Exception] = None, module: str = None) -> None:
        """
        에러 로그 출력
        
        Args:
            message (str): 에러 메시지
            exc_info (Exception, optional): 예외 정보
            module (str, optional): 모듈 이름
        """
        if module:
            message = f"[{module}] {message}"
        
        if exc_info:
            self.logger.error(message, exc_info=True)
        else:
            self.logger.error(message)
    
    async def send_error_to_channel(self, bot: discord.Client, message: str, exc_info: Optional[Exception] = None) -> None:
        """
        오류를 Discord 채널로 전송
        
        Args:
            bot (discord.Client): Discord 봇 인스턴스
            message (str): 에러 메시지
            exc_info (Exception, optional): 예외 정보
        """
        if not self.settings["error_channel_id"]:
            return
        
        try:
            channel = bot.get_channel(int(self.settings["error_channel_id"]))
            if not channel:
                log_warning(f"오류 보고 채널을 찾을 수 없습니다: {self.settings['error_channel_id']}")
                return
            
            # 현재 시간
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 오류 임베드 생성
            embed = discord.Embed(
                title="⚠️ 봇 오류 발생",
                description=f"**시간**: {now}\n**오류**: {message}",
                color=discord.Color.red()
            )
            
            # 예외 정보 추가
            if exc_info:
                import traceback
                tb = traceback.format_exception(type(exc_info), exc_info, exc_info.__traceback__)
                tb_text = ''.join(tb)
                
                # 임베드 필드 크기 제한으로 인해 내용이 너무 길면 잘라냄
                if len(tb_text) > 1000:
                    tb_text = tb_text[:997] + "..."
                
                embed.add_field(name="상세 오류", value=f"```python\n{tb_text}\n```", inline=False)
            
            await channel.send(embed=embed)
        except Exception as e:
            log_error(f"오류 보고 채널에 메시지 전송 중 오류 발생: {e}", e)
    
    def get_debug_status(self) -> Dict[str, Any]:
        """
        디버그 상태 정보 반환
        
        Returns:
            Dict[str, Any]: 디버그 상태 정보
        """
        return {
            "debug_mode": self.settings["debug_mode"],
            "verbose_debug": self.settings["verbose_debug"],
            "log_commands": self.settings["log_commands"],
            "log_to_file": self.settings["log_to_file"],
            "active_modules": list(self.active_modules),
            "module_debugging": self.settings["module_debugging"]
        }
    
    def create_debug_embed(self) -> discord.Embed:
        """
        디버그 상태 임베드 생성
        
        Returns:
            discord.Embed: 디버그 상태 임베드
        """
        embed = discord.Embed(
            title="🔍 디버그 상태",
            description="현재 디버그 설정 상태입니다.",
            color=discord.Color.blue()
        )
        
        # 기본 설정
        base_config = [
            f"디버그 모드: {'✅' if self.settings['debug_mode'] else '❌'}",
            f"상세 디버그: {'✅' if self.settings['verbose_debug'] else '❌'}",
            f"명령어 로깅: {'✅' if self.settings['log_commands'] else '❌'}",
            f"파일 로깅: {'✅' if self.settings['log_to_file'] else '❌'}"
        ]
        
        embed.add_field(name="기본 설정", value="\n".join(base_config), inline=False)
        
        # 활성화된 모듈
        if self.active_modules:
            active_modules = [f"- {module}" for module in sorted(self.active_modules)]
            
            # 필드 크기 제한으로 인해 긴 목록 처리
            if len(active_modules) > 15:
                module_chunks = [active_modules[i:i+15] for i in range(0, len(active_modules), 15)]
                
                for i, chunk in enumerate(module_chunks):
                    embed.add_field(
                        name=f"활성화된 모듈 ({i+1}/{len(module_chunks)})",
                        value="\n".join(chunk),
                        inline=True
                    )
            else:
                embed.add_field(name="활성화된 모듈", value="\n".join(active_modules), inline=True)
        
        # 모듈별 디버그 설정
        if self.settings["module_debugging"]:
            module_debug = []
            
            for module, enabled in sorted(self.settings["module_debugging"].items()):
                if module in self.active_modules:
                    module_debug.append(f"- {module}: {'✅' if enabled else '❌'}")
            
            if module_debug:
                # 필드 크기 제한으로 인해 긴 목록 처리
                if len(module_debug) > 15:
                    debug_chunks = [module_debug[i:i+15] for i in range(0, len(module_debug), 15)]
                    
                    for i, chunk in enumerate(debug_chunks):
                        embed.add_field(
                            name=f"모듈별 디버그 ({i+1}/{len(debug_chunks)})",
                            value="\n".join(chunk),
                            inline=True
                        )
                else:
                    embed.add_field(name="모듈별 디버그", value="\n".join(module_debug), inline=True)
        
        # 현재 시간
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed.set_footer(text=f"마지막 업데이트: {now}")
        
        return embed

# 디버그 매니저 인스턴스 (싱글톤)
debug_manager = DebugManager()