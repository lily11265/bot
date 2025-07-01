# cafe.py - 최적화된 버전

import asyncio
import datetime
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import discord
import aiofiles
from dataclasses import dataclass, field
from enum import Enum

from utility import (
get_user_inventory, update_user_inventory, get_batch_user_data,
cache_manager
)

logger = logging.getLogger(**name**)

# 설정 파일에서 로드

class CafeConfig:
“”“카페 설정 관리 클래스”””

```
def __init__(self, config_file: str = "cafe_config.json"):
    self.config_file = config_file
    self.config = self._load_config()

def _load_config(self) -> Dict:
    """설정 파일 로드"""
    default_config = {
        "cafe_channel_id": 1388391607983800382,
        "dice_bot_id": 218010938807287808,
        "admin_id": "1007172975222603798",
        "awakening_duration": 86400,  # 24시간 (초)
        "trade_timeout": 300,  # 5분 (초)
        "damage_values": {
            "individual": -30,
            "area": -20
        },
        "awakening_threshold": 90,
        "individual_damage_range": [4, 10],
        "area_damage_range": [1, 3],
        "member_names_file": "member_names.json"
    }
    
    try:
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                loaded_config = json.load(f)
                # 기본 설정과 병합
                default_config.update(loaded_config)
        else:
            # 기본 설정 파일 생성
            self._save_config(default_config)
            logger.info(f"기본 설정 파일 생성: {self.config_file}")
            
        return default_config
        
    except Exception as e:
        logger.error(f"설정 파일 로드 실패: {e}")
        return default_config

def _save_config(self, config: Dict):
    """설정 파일 저장"""
    try:
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"설정 파일 저장 실패: {e}")

def get(self, key: str, default=None):
    """설정값 가져오기"""
    return self.config.get(key, default)
```

class MemberNameManager:
“”“멤버 이름 관리 클래스”””

```
def __init__(self, config: CafeConfig):
    self.config = config
    self.member_names = self._load_member_names()
    self._name_cache = {}  # 파싱 결과 캐시

def _load_member_names(self) -> Set[str]:
    """멤버 이름 목록 로드"""
    names_file = self.config.get("member_names_file", "member_names.json")
    
    # 기본 멤버 이름 (하드코딩에서 이동)
    default_names = {
        "아카시 하지메", "펀처", "유진석", "휘슬", "배달기사", "페이",
        "로메즈 아가레스", "레이나 하트베인", "비비", "오카미 나오하",
        "카라트에크", "토트", "처용", "멀 플리시", "코발트윈드", "옥타",
        "베레니케", "안드라 블랙", "봉고 3호", "몰", "베니", "백야",
        "루치페르", "벨사이르 드라켄리트", "불스", "퓨어 메탈", "노 단투",
        "라록", "아카이브", "베터", "메르쿠리", "마크-112", "스푸트니크 2세",
        "이터니티", "커피머신"
    }
    
    try:
        if os.path.exists(names_file):
            with open(names_file, 'r', encoding='utf-8') as f:
                loaded_names = json.load(f)
                if isinstance(loaded_names, list):
                    return set(loaded_names)
                elif isinstance(loaded_names, dict):
                    return set(loaded_names.get("names", default_names))
        else:
            # 기본 파일 생성
            self._save_member_names(default_names)
            logger.info(f"기본 멤버 이름 파일 생성: {names_file}")
            
        return default_names
        
    except Exception as e:
        logger.error(f"멤버 이름 파일 로드 실패: {e}")
        return default_names

def _save_member_names(self, names: Set[str]):
    """멤버 이름 파일 저장"""
    names_file = self.config.get("member_names_file", "member_names.json")
    try:
        data = {
            "names": sorted(list(names)),
            "last_updated": datetime.now().isoformat()
        }
        with open(names_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"멤버 이름 파일 저장 실패: {e}")

def parse_name_and_health(self, display_name: str) -> Tuple[Optional[str], Optional[int]]:
    """디스플레이 이름에서 멤버 이름과 체력 추출 (캐시 사용)"""
    # 캐시 확인
    if display_name in self._name_cache:
        return self._name_cache[display_name]
    
    result = self._parse_name_and_health_internal(display_name)
    
    # 캐시 저장 (최대 100개)
    if len(self._name_cache) < 100:
        self._name_cache[display_name] = result
    
    return result

def _parse_name_and_health_internal(self, display_name: str) -> Tuple[Optional[str], Optional[int]]:
    """내부 파싱 로직"""
    logger.debug(f"이름과 체력 파싱: {display_name}")
    
    # 멤버 이름 찾기 (긴 이름부터 우선 처리)
    sorted_names = sorted(self.member_names, key=len, reverse=True)
    
    for member_name in sorted_names:
        if member_name in display_name:
            logger.debug(f"멤버 이름 찾음: {member_name}")
            
            # 이름 뒤의 숫자 찾기
            name_end = display_name.find(member_name) + len(member_name)
            remaining = display_name[name_end:]
            
            # 숫자 패턴 찾기 (개선된 정규식)
            health_patterns = [
                r'[/\s\-_:]*(\d+)',  # 구분자 다음 숫자
                r'(\d+)'  # 단순 숫자
            ]
            
            for pattern in health_patterns:
                match = re.search(pattern, remaining)
                if match:
                    health = int(match.group(1))
                    logger.debug(f"체력 찾음: {health}")
                    return member_name, health
            
            # 전체에서 마지막 숫자 찾기
            all_numbers = re.findall(r'\d+', display_name)
            if all_numbers:
                health = int(all_numbers[-1])
                logger.debug(f"체력 찾음 (전체): {health}")
                return member_name, health
            else:
                logger.debug("체력을 찾을 수 없음")
                return member_name, None
    
    logger.debug(f"멤버 이름과 일치하지 않음: {display_name}")
    return None, None

def find_member_by_name(self, guild: discord.Guild, member_name: str) -> Optional[discord.Member]:
    """멤버 이름으로 Discord 멤버 찾기 (최적화)"""
    cache_key = f"member_{guild.id}_{member_name}"
    
    logger.debug(f"멤버 찾기: {member_name} (길드: {guild.name})")
    
    # 정확한 일치 우선
    for member in guild.members:
        if (member_name in member.display_name or 
            member.name == member_name):
            logger.debug(f"멤버 찾음: {member.display_name} (ID: {member.id})")
            return member
    
    # 대소문자 무시 검색
    for member in guild.members:
        if (member_name.lower() in member.display_name.lower() or
            member_name.lower() == member.name.lower()):
            logger.debug(f"멤버 찾음 (대소문자 무시): {member.display_name}")
            return member
    
    # 정리된 이름으로 검색
    clean_member_name = re.sub(r'[^\w가-힣]', '', member_name)
    for member in guild.members:
        clean_display = re.sub(r'[^\w가-힣]', '', member.display_name)
        if clean_member_name in clean_display:
            logger.debug(f"멤버 찾음 (정리된 이름): {member.display_name}")
            return member
    
    logger.warning(f"멤버를 찾을 수 없음: {member_name}")
    return None
```

@dataclass
class AwakeningSession:
“”“각성 세션 데이터”””
user_id: str
start_time: datetime
end_time: datetime
original_nick: str
task: Optional[asyncio.Task] = None

@dataclass
class TradeRecord:
“”“거래 기록”””
timestamp: datetime
expires_at: datetime

class CafeDiceSystem:
“”“최적화된 카페 주사위 시스템”””

```
def __init__(self, bot):
    self.bot = bot
    self.config = CafeConfig()
    self.member_manager = MemberNameManager(self.config)
    
    # 파일 경로
    self.awakening_file = "data/awakening_data.json"
    self.daily_dice_file = "data/daily_dice_data.json"
    
    # 메모리 구조 최적화
    self.awakening_sessions: Dict[str, AwakeningSession] = {}
    self.daily_dice_users: Set[str] = set()
    self.recent_trades: Dict[str, TradeRecord] = {}
    
    # 백그라운드 작업
    self.cleanup_task = None
    self.save_task = None
    
    # 데이터 디렉토리 생성
    os.makedirs("data", exist_ok=True)
    
    logger.info("카페 주사위 시스템 초기화 시작")
    
    # 초기화
    self._initialize_system()
    
def _initialize_system(self):
    """시스템 초기화"""
    # 저장된 데이터 로드
    self._load_awakening_data()
    self._load_daily_dice_data()
    
    # 백그라운드 작업 시작
    self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
    self.save_task = asyncio.create_task(self._periodic_save())
    
    logger.info("카페 주사위 시스템 초기화 완료")

async def record_trade_to_admin(self, user_id: str):
    """Admin 거래 기록 (최적화)"""
    expires_at = datetime.now() + timedelta(seconds=self.config.get("trade_timeout", 300))
    
    self.recent_trades[user_id] = TradeRecord(
        timestamp=datetime.now(),
        expires_at=expires_at
    )
    
    logger.info(f"거래 기록: {user_id} -> Admin")

def _check_recent_trade(self, user_id: str) -> bool:
    """최근 거래 확인 (최적화)"""
    if user_id not in self.recent_trades:
        return False
    
    trade_record = self.recent_trades[user_id]
    if datetime.now() > trade_record.expires_at:
        # 만료된 기록 즉시 삭제
        del self.recent_trades[user_id]
        return False
    
    return True

async def handle_dice_message(self, message: discord.Message):
    """주사위 메시지 처리 (최적화)"""
    try:
        # 기본 검증
        if not self._validate_message(message):
            return False
        
        logger.info(f"주사위 봇 메시지 감지: {message.content}")
        
        # 메시지 파싱
        parse_result = self._parse_dice_message(message.content)
        if not parse_result:
            logger.warning(f"메시지 파싱 실패: {message.content}")
            return False
        
        display_name, dice_value = parse_result
        logger.info(f"파싱 성공 - 이름: {display_name}, 주사위값: {dice_value}")
        
        # 멤버 찾기
        member_name, parsed_health = self.member_manager.parse_name_and_health(display_name)
        if not member_name:
            logger.error(f"멤버 이름과 일치하지 않음: {display_name}")
            return False
        
        member = self.member_manager.find_member_by_name(message.guild, member_name)
        if not member:
            logger.error(f"멤버를 찾을 수 없음: {member_name}")
            return False
        
        # 거래 확인
        user_id = str(member.id)
        if not self._check_recent_trade(user_id):
            logger.warning(f"{member.display_name}님은 최근 거래 기록이 없음")
            # 거래 없이도 처리할지는 설정에 따라
            if self.config.get("require_trade", False):
                return False
        
        # 주사위 결과 처리
        await self._process_dice_result(member, dice_value)
        
        # 일일 기록 업데이트
        self.daily_dice_users.add(user_id)
        
        # 거래 기록 삭제
        self.recent_trades.pop(user_id, None)
        
        logger.info(f"주사위 처리 완료: {member.display_name}")
        return True
        
    except Exception as e:
        logger.error(f"주사위 처리 실패: {e}", exc_info=True)
        return False

def _validate_message(self, message: discord.Message) -> bool:
    """메시지 유효성 검증"""
    return (
        message.channel.id == self.config.get("cafe_channel_id") and
        message.author.id == self.config.get("dice_bot_id") and
        not message.author.bot is False  # 봇 메시지여야 함
    )

def _parse_dice_message(self, content: str) -> Optional[Tuple[str, int]]:
    """주사위 메시지 파싱 (개선된 정규식)"""
    # 여러 패턴 지원
    patterns = [
        r"`(.+?)`님이.*?주사위를 굴려.*?(\d+).*?나왔습니다",
        r"(.+?)님이.*?주사위.*?(\d+)",
        r"`(.+?)`.*?(\d+)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            display_name = match.group(1).strip()
            dice_value = int(match.group(2))
            logger.debug(f"파싱 성공 (패턴: {pattern}): {display_name}, {dice_value}")
            return (display_name, dice_value)
    
    logger.debug("모든 패턴 파싱 실패")
    return None

async def _process_dice_result(self, member: discord.Member, dice_value: int):
    """주사위 결과 처리 (최적화)"""
    config = self.config
    
    if dice_value >= config.get("awakening_threshold", 90):
        logger.info(f"각성 효과 처리: {dice_value}")
        await self._handle_awakening(member)
        
    elif config.get("individual_damage_range", [4, 10])[0] <= dice_value <= config.get("individual_damage_range", [4, 10])[1]:
        damage = config.get("damage_values", {}).get("individual", -30)
        logger.info(f"개인 데미지 처리: {damage}")
        await self._handle_damage(member, damage)
        
    elif config.get("area_damage_range", [1, 3])[0] <= dice_value <= config.get("area_damage_range", [1, 3])[1]:
        logger.info("범위 데미지 처리")
        await self._handle_area_damage(member.guild.get_channel(self.config.get("cafe_channel_id")), member)
    else:
        logger.info(f"처리 없음 - 주사위값: {dice_value}")

async def handle_trade_command(self, user_id: str, target_id: str, amount: int):
    """거래 명령어 처리"""
    admin_id = self.config.get("admin_id")
    if target_id == admin_id and amount == 1:
        await self.record_trade_to_admin(user_id)

async def _handle_awakening(self, member: discord.Member):
    """각성 효과 처리 (최적화)"""
    user_id = str(member.id)
    
    # 중복 처리 방지
    if user_id in self.awakening_sessions:
        logger.info(f"{member.display_name}님은 이미 각성 상태")
        return
    
    # 오늘 주사위 확인
    if user_id in self.daily_dice_users:
        logger.info(f"{member.display_name}님은 오늘 이미 주사위를 굴림")
        return
    
    # 닉네임 변경
    await self._apply_awakening_effect(member)

async def _apply_awakening_effect(self, member: discord.Member):
    """각성 효과 적용"""
    user_id = str(member.id)
    current_nick = member.display_name
    
    if current_nick.startswith("[각성]"):
        logger.info(f"{member.display_name}님은 이미 [각성] 효과 보유")
        return
    
    new_nick = f"[각성]{current_nick}"
    
    try:
        await member.edit(nick=new_nick[:32])
        logger.info(f"{member.display_name}님에게 각성 효과 부여 성공")
        
        # 세션 생성
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=self.config.get("awakening_duration", 86400))
        
        # 타이머 시작
        timer_task = asyncio.create_task(self._awakening_timer(user_id, self.config.get("awakening_duration", 86400)))
        
        self.awakening_sessions[user_id] = AwakeningSession(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            original_nick=current_nick,
            task=timer_task
        )
        
        # 캐시에 저장
        await cache_manager.set(
            f"awakening_end:{user_id}", 
            end_time.isoformat(), 
            ex=self.config.get("awakening_duration", 86400)
        )
        
    except discord.Forbidden:
        logger.error(f"닉네임 변경 권한 없음: {member.display_name}")
    except Exception as e:
        logger.error(f"각성 효과 부여 실패: {e}")

async def _awakening_timer(self, user_id: str, duration: float):
    """각성 타이머"""
    try:
        await asyncio.sleep(duration)
        await self._remove_awakening_effect(user_id)
    except asyncio.CancelledError:
        logger.debug(f"각성 타이머 취소됨: {user_id}")
    except Exception as e:
        logger.error(f"각성 타이머 실패: {e}")

async def _remove_awakening_effect(self, user_id: str):
    """각성 효과 제거"""
    try:
        session = self.awakening_sessions.get(user_id)
        if not session:
            return
        
        # 멤버 찾기
        member = None
        for guild in self.bot.guilds:
            member = guild.get_member(int(user_id))
            if member:
                break
        
        if member and member.display_name.startswith("[각성]"):
            new_nick = member.display_name[4:]
            try:
                await member.edit(nick=new_nick)
                logger.info(f"{user_id}의 각성 효과 제거 성공")
            except Exception as e:
                logger.error(f"각성 제거 실패: {e}")
        
        # 세션 정리
        if user_id in self.awakening_sessions:
            del self.awakening_sessions[user_id]
        
        # 캐시 정리
        await cache_manager.delete(f"awakening_end:{user_id}")
        
    except Exception as e:
        logger.error(f"각성 효과 제거 실패: {e}")

async def _handle_damage(self, member: discord.Member, damage: int):
    """데미지 처리"""
    user_id = str(member.id)
    logger.info(f"데미지 처리: {member.display_name}, 데미지: {damage}")
    
    # 현재 체력 확인
    _, current_health = self.member_manager.parse_name_and_health(member.display_name)
    
    if current_health is None:
        logger.warning(f"{member.display_name}의 체력을 찾을 수 없음")
        return
    
    # 새 체력 계산
    new_health = max(0, current_health + damage)
    logger.info(f"체력 변경: {current_health} -> {new_health}")
    
    # 체력 업데이트
    await self._update_member_health(member, new_health)

async def _handle_area_damage(self, channel: discord.TextChannel, dice_roller: discord.Member):
    """범위 데미지 처리 (최적화)"""
    logger.info(f"범위 데미지 처리: {dice_roller.display_name}")
    
    # 5분간 메시지 수집 (최적화)
    cutoff_time = datetime.utcnow() - timedelta(minutes=5)
    affected_members = set()
    channel_taggers = set()
    
    try:
        async for msg in channel.history(after=cutoff_time, limit=100):
            if msg.author.bot:
                continue
            
            # 채널 태그 확인
            if re.search(r'<#\d+>', msg.content):
                channel_taggers.add(msg.author.id)
            
            affected_members.add(msg.author)
        
        # 대상 필터링
        targets = [
            m for m in affected_members 
            if m.id not in channel_taggers and m.id != dice_roller.id
        ]
        
        logger.info(f"범위 데미지 대상: {len(targets)}명")
        
        # 데미지 적용 (배치 처리)
        damage_value = self.config.get("damage_values", {}).get("area", -20)
        tasks = []
        
        for member in targets[:10]:  # 최대 10명으로 제한
            tasks.append(self._handle_damage(member, damage_value))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    except Exception as e:
        logger.error(f"범위 데미지 처리 실패: {e}")

async def _update_member_health(self, member: discord.Member, new_health: int):
    """멤버 체력 업데이트 (닉네임 + 스프레드시트)"""
    user_id = str(member.id)
    current_nick = member.display_name
    
    try:
        # 닉네임 업데이트
        health_removed = re.sub(r'\d+(?!.*\d)', '', current_nick).strip()
        
        # 사망 처리
        if new_health <= 0:
            if not health_removed.startswith("[사망]"):
                health_removed = f"[사망]{health_removed}"
        else:
            if health_removed.startswith("[사망]"):
                health_removed = health_removed[4:]
        
        new_nick = f"{health_removed} {new_health}".strip()
        
        # 닉네임 변경
        await member.edit(nick=new_nick[:32])
        logger.info(f"닉네임 체력 업데이트: {member.name} -> {new_health}")
        
        # 스프레드시트 업데이트
        await self._update_spreadsheet_health(user_id, new_health)
        
    except discord.Forbidden:
        logger.error(f"닉네임 변경 권한 없음: {member.display_name}")
    except Exception as e:
        logger.error(f"체력 업데이트 실패: {e}")

async def _update_spreadsheet_health(self, user_id: str, new_health: int):
    """스프레드시트 체력 업데이트"""
    try:
        user_data = await get_user_inventory(user_id)
        if not user_data:
            logger.warning(f"유저 데이터를 찾을 수 없음: {user_id}")
            return
        
        success = await update_user_inventory(
            user_id,
            coins=user_data.get("coins"),
            items=user_data.get("items"),
            outfits=user_data.get("outfits"),
            physical_status=user_data.get("physical_status"),
            corruption=user_data.get("corruption"),
            health=str(new_health)
        )
        
        if success:
            logger.info(f"스프레드시트 체력 업데이트 성공: {user_id} -> {new_health}")
        else:
            logger.error(f"스프레드시트 체력 업데이트 실패: {user_id}")
            
    except Exception as e:
        logger.error(f"스프레드시트 업데이트 오류: {e}")

def _load_awakening_data(self):
    """각성 데이터 로드 (최적화)"""
    if not os.path.exists(self.awakening_file):
        return
        
    try:
        with open(self.awakening_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        current_time = datetime.now()
        restored_count = 0
        
        for user_id, session_data in data.items():
            try:
                end_time = datetime.fromisoformat(session_data['end_time'])
                if end_time > current_time:
                    # 유효한 세션 복원
                    remaining = (end_time - current_time).total_seconds()
                    
                    timer_task = asyncio.create_task(self._awakening_timer(user_id, remaining))
                    
                    self.awakening_sessions[user_id] = AwakeningSession(
                        user_id=user_id,
                        start_time=datetime.fromisoformat(session_data['start_time']),
                        end_time=end_time,
                        original_nick=session_data.get('original_nick', ''),
                        task=timer_task
                    )
                    restored_count += 1
                    
            except (ValueError, KeyError) as e:
                logger.warning(f"잘못된 각성 데이터: {user_id} - {e}")
                continue
        
        logger.info(f"각성 데이터 로드 완료: {restored_count}명 복원")
        
    except Exception as e:
        logger.error(f"각성 데이터 로드 실패: {e}")

def _load_daily_dice_data(self):
    """일일 주사위 데이터 로드"""
    if not os.path.exists(self.daily_dice_file):
        return
        
    try:
        with open(self.daily_dice_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        today = datetime.now().strftime('%Y-%m-%d')
        if data.get('date') == today:
            self.daily_dice_users = set(data.get('users', []))
            logger.info(f"오늘 주사위 굴린 유저: {len(self.daily_dice_users)}명")
        else:
            logger.info("날짜 변경으로 일일 주사위 데이터 초기화")
            self.daily_dice_users = set()
            asyncio.create_task(self._save_daily_dice_data())
            
    except Exception as e:
        logger.error(f"일일 주사위 데이터 로드 실패: {e}")

async def _save_awakening_data(self):
    """각성 데이터 저장 (비동기)"""
    try:
        data = {}
        for user_id, session in self.awakening_sessions.items():
            if session.task and not session.task.done():
                data[user_id] = {
                    'start_time': session.start_time.isoformat(),
                    'end_time': session.end_time.isoformat(),
                    'original_nick': session.original_nick
                }
        
        async with aiofiles.open(self.awakening_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        
        logger.debug(f"각성 데이터 저장: {len(data)}명")
        
    except Exception as e:
        logger.error(f"각성 데이터 저장 실패: {e}")

async def _save_daily_dice_data(self):
    """일일 주사위 데이터 저장 (비동기)"""
    try:
        data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'users': list(self.daily_dice_users)
        }
        
        async with aiofiles.open(self.daily_dice_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        
        logger.debug(f"일일 주사위 데이터 저장: {len(self.daily_dice_users)}명")
        
    except Exception as e:
        logger.error(f"일일 주사위 데이터 저장 실패: {e}")

async def _periodic_cleanup(self):
    """주기적 정리 작업 (최적화)"""
    while True:
        try:
            await asyncio.sleep(1800)  # 30분마다
            
            current_time = datetime.now()
            
            # 자정에 일일 데이터 초기화
            if current_time.hour == 0 and current_time.minute < 30:
                self.daily_dice_users.clear()
                await self._save_daily_dice_data()
                logger.info("일일 주사위 데이터 초기화")
            
            # 완료된 각성 세션 정리
            completed_sessions = [
                uid for uid, session in self.awakening_sessions.items()
                if session.task and session.task.done()
            ]
            
            for uid in completed_sessions:
                del self.awakening_sessions[uid]
            
            # 만료된 거래 기록 정리
            expired_trades = [
                uid for uid, record in self.recent_trades.items()
                if current_time > record.expires_at
            ]
            
            for uid in expired_trades:
                del self.recent_trades[uid]
            
            if completed_sessions or expired_trades:
                logger.debug(f"정리 완료 - 각성: {len(completed_sessions)}, 거래: {len(expired_trades)}")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"정리 작업 실패: {e}")

async def _periodic_save(self):
    """주기적 저장 작업"""
    while True:
        try:
            await asyncio.sleep(600)  # 10분마다
            await asyncio.gather(
                self._save_awakening_data(),
                self._save_daily_dice_data(),
                return_exceptions=True
            )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"주기적 저장 실패: {e}")

async def shutdown(self):
    """시스템 종료 (최적화)"""
    logger.info("카페 시스템 종료 시작")
    
    # 백그라운드 작업 취소
    tasks_to_cancel = [self.cleanup_task, self.save_task]
    
    for task in tasks_to_cancel:
        if task and not task.done():
            task.cancel()
    
    # 각성 타이머 취소
    for session in self.awakening_sessions.values():
        if session.task and not session.task.done():
            session.task.cancel()
    
    # 모든 취소된 작업 완료 대기
    all_tasks = tasks_to_cancel + [s.task for s in self.awakening_sessions.values() if s.task]
    if all_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*all_tasks, return_exceptions=True),
                timeout=5.0
            )
        except asyncio.TimeoutError:
            logger.warning("일부 작업 취소가 타임아웃됨")
    
    # 최종 데이터 저장
    try:
        await asyncio.wait_for(
            asyncio.gather(
                self._save_awakening_data(),
                self._save_daily_dice_data(),
                return_exceptions=True
            ),
            timeout=5.0
        )
    except asyncio.TimeoutError:
        logger.warning("최종 저장이 타임아웃됨")
    
    logger.info("카페 시스템 종료 완료")
```

# 전역 인스턴스

cafe_dice_system = None

def init_cafe_system(bot):
“”“카페 시스템 초기화”””
global cafe_dice_system
logger.info(“카페 시스템 초기화”)
cafe_dice_system = CafeDiceSystem(bot)
return cafe_dice_system

def get_cafe_system():
“”“카페 시스템 인스턴스 반환”””
return cafe_dice_system

async def handle_message(message: discord.Message):
“”“메시지 처리”””
system = get_cafe_system()
if system and message.author.bot and message.author.id == system.config.get(“dice_bot_id”):
return await system.handle_dice_message(message)
return False

async def handle_trade_to_admin(user_id: str, target_id: str, amount: int):
“”“Admin 거래 처리”””
system = get_cafe_system()
if system:
await system.handle_trade_command(user_id, target_id, amount)