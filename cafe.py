# cafe.py - 완전 재작성 버전

import asyncio
import logging
import re
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import weakref
import discord

from utility import (
get_user_inventory, update_user_inventory, get_batch_user_data,
cache_manager
)

logger = logging.getLogger(**name**)

# === 상수 및 설정 ===

class CafeConfig:
“”“카페 시스템 설정”””
CAFE_CHANNEL_ID = 1388391607983800382
DICE_BOT_ID = 218010938807287808
ADMIN_ID = “1007172975222603798”
AWAKENING_DURATION = 86400  # 24시간
CLEANUP_INTERVAL = 1800  # 30분
SESSION_TIMEOUT = 1800  # 30분
MAX_DICE_PER_DAY = 1  # 일일 주사위 제한
TRADE_TIMEOUT = 300  # 거래 기록 5분
HEALTH_UPDATE_DELAY = 0.5  # 체력 업데이트 간 지연

class DiceRange(Enum):
“”“주사위 결과 범위”””
AWAKENING = (90, 100)  # 각성
PERSONAL_DAMAGE = (4, 10)  # 개인 데미지
AREA_DAMAGE = (1, 3)  # 범위 데미지

@dataclass
class MemberData:
“”“멤버 정보”””
discord_id: int
name: str
display_name: str
current_health: Optional[int] = None
has_awakening: bool = False

@dataclass
class DiceResult:
“”“주사위 결과 데이터”””
member: MemberData
dice_value: int
timestamp: datetime
processed: bool = False

@dataclass
class AwakeningSession:
“”“각성 세션 정보”””
user_id: str
start_time: datetime
end_time: datetime
task: Optional[asyncio.Task] = None
original_nickname: str = “”

# === 멤버 이름 데이터베이스 ===

class MemberDatabase:
“”“하드코딩된 멤버 이름 데이터베이스”””

```
MEMBER_NAMES = {
    "아카시 하지메", "펀처", "유진석", "휘슬", "배달기사", "페이",
    "로메즈 아가레스", "레이나 하트베인", "비비", "오카미 나오하",
    "카라트에크", "토트", "처용", "멀 플리시", "코발트윈드", "옥타",
    "베레니케", "안드라 블랙", "봉고 3호", "몰", "베니", "백야",
    "루치페르", "벨사이르 드라켄리트", "불스", "퓨어 메탈", "노 단투",
    "라록", "아카이브", "베터", "메르쿠리", "마크-112", "스푸트니크 2세",
    "이터니티", "커피머신"
}

@classmethod
def extract_member_info(cls, display_name: str) -> Tuple[Optional[str], Optional[int]]:
    """디스플레이 이름에서 멤버 이름과 체력 추출"""
    # 하드코딩된 이름 찾기
    for member_name in cls.MEMBER_NAMES:
        if member_name in display_name:
            # 이름 이후 부분에서 숫자 찾기
            name_end = display_name.find(member_name) + len(member_name)
            remaining = display_name[name_end:]
            
            # 숫자 추출
            numbers = re.findall(r'\d+', remaining)
            if numbers:
                return member_name, int(numbers[0])
            else:
                # 전체에서 마지막 숫자 찾기
                all_numbers = re.findall(r'\d+', display_name)
                if all_numbers:
                    return member_name, int(all_numbers[-1])
            
            return member_name, None
    
    return None, None

@classmethod
def find_discord_member(cls, guild: discord.Guild, member_name: str) -> Optional[discord.Member]:
    """Discord 길드에서 멤버 찾기"""
    # 정확한 일치 우선
    for member in guild.members:
        if member_name in member.display_name or member_name == member.name:
            return member
    
    # 대소문자 무시 검색
    for member in guild.members:
        if (member_name.lower() in member.display_name.lower() or 
            member_name.lower() == member.name.lower()):
            return member
    
    # 정리된 이름으로 검색
    clean_name = re.sub(r'[^\w가-힣]', '', member_name)
    for member in guild.members:
        clean_display = re.sub(r'[^\w가-힣]', '', member.display_name)
        clean_username = re.sub(r'[^\w가-힣]', '', member.name)
        
        if clean_name in clean_display or clean_name == clean_username:
            return member
    
    return None
```

# === 파일 관리자 ===

class DataFileManager:
“”“데이터 파일 관리”””

```
def __init__(self):
    self.awakening_file = "awakening_data.json"
    self.daily_dice_file = "daily_dice_data.json"
    self.trade_records_file = "trade_records.json"

async def load_awakening_data(self) -> Dict:
    """각성 데이터 로드"""
    return await self._load_json_file(self.awakening_file)

async def save_awakening_data(self, data: Dict) -> bool:
    """각성 데이터 저장"""
    return await self._save_json_file(self.awakening_file, data)

async def load_daily_dice_data(self) -> Dict:
    """일일 주사위 데이터 로드"""
    data = await self._load_json_file(self.daily_dice_file)
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 날짜가 다르면 초기화
    if data.get('date') != today:
        return {'date': today, 'users': []}
    
    return data

async def save_daily_dice_data(self, users: Set[str]) -> bool:
    """일일 주사위 데이터 저장"""
    data = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'users': list(users)
    }
    return await self._save_json_file(self.daily_dice_file, data)

async def load_trade_records(self) -> Dict:
    """거래 기록 로드"""
    return await self._load_json_file(self.trade_records_file)

async def save_trade_records(self, data: Dict) -> bool:
    """거래 기록 저장"""
    return await self._save_json_file(self.trade_records_file, data)

async def _load_json_file(self, filepath: str) -> Dict:
    """JSON 파일 비동기 로드"""
    if not os.path.exists(filepath):
        return {}
    
    try:
        loop = asyncio.get_event_loop()
        with open(filepath, 'r', encoding='utf-8') as f:
            content = await loop.run_in_executor(None, f.read)
            return json.loads(content)
    except Exception as e:
        logger.error(f"파일 로드 실패 {filepath}: {e}")
        return {}

async def _save_json_file(self, filepath: str, data: Dict) -> bool:
    """JSON 파일 비동기 저장"""
    try:
        loop = asyncio.get_event_loop()
        temp_file = f"{filepath}.tmp"
        
        def write_file():
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, filepath)
        
        await loop.run_in_executor(None, write_file)
        return True
        
    except Exception as e:
        logger.error(f"파일 저장 실패 {filepath}: {e}")
        return False
```

# === 메시지 파서 ===

class DiceMessageParser:
“”“주사위 메시지 파싱”””

```
DICE_PATTERN = re.compile(r"`(.+?)`님이.*?주사위를 굴려.*?(\d+).*?나왔습니다")

@classmethod
def parse_dice_message(cls, content: str) -> Optional[Tuple[str, int]]:
    """주사위 메시지 파싱"""
    match = cls.DICE_PATTERN.search(content)
    if match:
        return match.group(1), int(match.group(2))
    return None

@classmethod
def get_dice_range_type(cls, dice_value: int) -> Optional[DiceRange]:
    """주사위 값에 따른 처리 타입 반환"""
    for dice_range in DiceRange:
        min_val, max_val = dice_range.value
        if min_val <= dice_value <= max_val:
            return dice_range
    return None
```

# === 각성 관리자 ===

class AwakeningManager:
“”“각성 효과 관리”””

```
def __init__(self, file_manager: DataFileManager):
    self.file_manager = file_manager
    self.active_sessions: Dict[str, AwakeningSession] = {}
    self._lock = asyncio.Lock()

async def initialize(self) -> None:
    """초기화 - 저장된 각성 상태 복원"""
    data = await self.file_manager.load_awakening_data()
    restored_count = 0
    
    for user_id, session_data in data.items():
        try:
            end_time = datetime.fromisoformat(session_data['end_time'])
            if end_time > datetime.now():
                remaining = (end_time - datetime.now()).total_seconds()
                await self._start_awakening_timer(user_id, remaining, 
                                                session_data.get('original_nickname', ''))
                restored_count += 1
        except Exception as e:
            logger.error(f"각성 세션 복원 실패 {user_id}: {e}")
    
    logger.info(f"각성 세션 {restored_count}개 복원됨")

async def apply_awakening(self, member: discord.Member) -> bool:
    """각성 효과 적용"""
    user_id = str(member.id)
    
    async with self._lock:
        # 이미 각성 상태인지 확인
        if user_id in self.active_sessions:
            logger.info(f"{member.display_name}은 이미 각성 상태")
            return False
        
        # 닉네임에 [각성] 추가
        current_nick = member.display_name
        if current_nick.startswith("[각성]"):
            logger.info(f"{member.display_name}은 이미 [각성] 효과 보유")
            return False
        
        try:
            new_nick = f"[각성]{current_nick}"[:32]  # Discord 제한
            await member.edit(nick=new_nick)
            
            # 24시간 타이머 시작
            await self._start_awakening_timer(user_id, CafeConfig.AWAKENING_DURATION, current_nick)
            
            logger.info(f"{member.display_name}에게 각성 효과 부여")
            return True
            
        except discord.Forbidden:
            logger.error(f"닉네임 변경 권한 없음: {member.display_name}")
            return False
        except Exception as e:
            logger.error(f"각성 효과 부여 실패: {e}")
            return False

async def _start_awakening_timer(self, user_id: str, duration: float, original_nick: str = "") -> None:
    """각성 타이머 시작"""
    # 기존 타이머 취소
    if user_id in self.active_sessions:
        if self.active_sessions[user_id].task:
            self.active_sessions[user_id].task.cancel()
    
    # 새 세션 생성
    end_time = datetime.now() + timedelta(seconds=duration)
    task = asyncio.create_task(self._remove_awakening_after(user_id, duration))
    
    session = AwakeningSession(
        user_id=user_id,
        start_time=datetime.now(),
        end_time=end_time,
        task=task,
        original_nickname=original_nick
    )
    
    self.active_sessions[user_id] = session
    await self._save_awakening_data()
    
    logger.debug(f"각성 타이머 시작: {user_id}, {duration}초")

async def _remove_awakening_after(self, user_id: str, duration: float) -> None:
    """지정된 시간 후 각성 효과 제거"""
    try:
        await asyncio.sleep(duration)
        await self._remove_awakening(user_id)
    except asyncio.CancelledError:
        logger.debug(f"각성 타이머 취소됨: {user_id}")
    except Exception as e:
        logger.error(f"각성 제거 실패: {e}")

async def _remove_awakening(self, user_id: str) -> None:
    """각성 효과 제거"""
    if user_id not in self.active_sessions:
        return
    
    session = self.active_sessions[user_id]
    
    # Discord 멤버 찾기
    member = None
    # bot 인스턴스는 전역에서 접근 가능하다고 가정
    try:
        from main import bot
        for guild in bot.guilds:
            member = guild.get_member(int(user_id))
            if member:
                break
    except:
        logger.warning(f"봇 인스턴스 접근 실패")
    
    if member and member.display_name.startswith("[각성]"):
        try:
            # 원래 닉네임으로 복원 또는 [각성] 제거
            if session.original_nickname:
                new_nick = session.original_nickname
            else:
                new_nick = member.display_name[4:]  # "[각성]" 제거
            
            await member.edit(nick=new_nick)
            logger.info(f"{user_id}의 각성 효과 제거 완료")
        except Exception as e:
            logger.error(f"각성 제거 실패: {e}")
    
    # 세션 정리
    del self.active_sessions[user_id]
    await self._save_awakening_data()

async def _save_awakening_data(self) -> None:
    """각성 데이터 저장"""
    data = {}
    for user_id, session in self.active_sessions.items():
        if session.task and not session.task.done():
            data[user_id] = {
                'end_time': session.end_time.isoformat(),
                'original_nickname': session.original_nickname,
                'started_at': session.start_time.isoformat()
            }
    
    await self.file_manager.save_awakening_data(data)

async def cleanup_expired_sessions(self) -> None:
    """만료된 세션 정리"""
    expired_users = []
    for user_id, session in self.active_sessions.items():
        if session.task and session.task.done():
            expired_users.append(user_id)
    
    for user_id in expired_users:
        del self.active_sessions[user_id]
    
    if expired_users:
        await self._save_awakening_data()
        logger.debug(f"만료된 각성 세션 {len(expired_users)}개 정리")

def is_awakened(self, user_id: str) -> bool:
    """각성 상태 확인"""
    return user_id in self.active_sessions

async def shutdown(self) -> None:
    """종료 처리"""
    for session in self.active_sessions.values():
        if session.task and not session.task.done():
            session.task.cancel()
    
    await self._save_awakening_data()
```

# === 체력 관리자 ===

class HealthManager:
“”“체력 관리”””

```
@staticmethod
def extract_health_from_name(display_name: str) -> Optional[int]:
    """닉네임에서 체력 추출"""
    member_name, health = MemberDatabase.extract_member_info(display_name)
    if health is not None:
        return health
    
    # 폴백: 마지막 숫자
    numbers = re.findall(r'\d+', display_name)
    return int(numbers[-1]) if numbers else None

@staticmethod
async def update_member_health(member: discord.Member, new_health: int) -> bool:
    """멤버 체력 업데이트 (닉네임 + 스프레드시트)"""
    user_id = str(member.id)
    current_nick = member.display_name
    
    try:
        # 닉네임 업데이트
        success_nick = await HealthManager._update_nickname_health(member, new_health)
        
        # 스프레드시트 업데이트
        success_sheet = await HealthManager._update_spreadsheet_health(user_id, new_health)
        
        if success_nick and success_sheet:
            logger.info(f"{member.display_name} 체력 업데이트 성공: {new_health}")
            return True
        else:
            logger.warning(f"{member.display_name} 체력 업데이트 부분 실패")
            return False
            
    except Exception as e:
        logger.error(f"체력 업데이트 실패: {e}")
        return False

@staticmethod
async def _update_nickname_health(member: discord.Member, new_health: int) -> bool:
    """닉네임 체력 업데이트"""
    try:
        current_nick = member.display_name
        
        # 기존 숫자 제거
        health_removed = re.sub(r'\d+(?!.*\d)', '', current_nick).strip()
        
        # [사망] 효과 처리
        if new_health <= 0:
            if not health_removed.startswith("[사망]"):
                health_removed = f"[사망]{health_removed}"
        else:
            if health_removed.startswith("[사망]"):
                health_removed = health_removed[4:]
        
        # 새 닉네임 생성
        new_nick = f"{health_removed} {new_health}"[:32]
        await member.edit(nick=new_nick)
        
        return True
        
    except discord.Forbidden:
        logger.error(f"닉네임 변경 권한 없음: {member.display_name}")
        return False
    except Exception as e:
        logger.error(f"닉네임 업데이트 실패: {e}")
        return False

@staticmethod
async def _update_spreadsheet_health(user_id: str, new_health: int) -> bool:
    """스프레드시트 체력 업데이트"""
    try:
        user_data = await get_user_inventory(user_id)
        if not user_data:
            logger.warning(f"유저 데이터를 찾을 수 없음: {user_id}")
            return False
        
        success = await update_user_inventory(
            user_id,
            coins=user_data.get("coins"),
            items=user_data.get("items"),
            outfits=user_data.get("outfits"),
            physical_status=user_data.get("physical_status"),
            corruption=user_data.get("corruption"),
            health=str(new_health)
        )
        
        return success
        
    except Exception as e:
        logger.error(f"스프레드시트 업데이트 실패: {e}")
        return False
```

# === 거래 추적기 ===

class TradeTracker:
“”“거래 추적”””

```
def __init__(self, file_manager: DataFileManager):
    self.file_manager = file_manager
    self.recent_trades: Dict[str, datetime] = {}
    self._lock = asyncio.Lock()

async def initialize(self) -> None:
    """초기화"""
    data = await self.file_manager.load_trade_records()
    
    # 유효한 거래 기록만 복원 (5분 이내)
    current_time = datetime.now()
    for user_id, timestamp_str in data.items():
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            if (current_time - timestamp).total_seconds() <= CafeConfig.TRADE_TIMEOUT:
                self.recent_trades[user_id] = timestamp
        except Exception as e:
            logger.error(f"거래 기록 복원 실패 {user_id}: {e}")

async def record_trade(self, user_id: str) -> None:
    """거래 기록"""
    async with self._lock:
        self.recent_trades[user_id] = datetime.now()
        logger.info(f"거래 기록: {user_id}")
        
        # 파일 저장
        await self._save_trade_records()
        
        # 자동 만료 설정
        asyncio.create_task(self._expire_trade_after(user_id, CafeConfig.TRADE_TIMEOUT))

def has_recent_trade(self, user_id: str) -> bool:
    """최근 거래 확인"""
    if user_id not in self.recent_trades:
        return False
    
    elapsed = (datetime.now() - self.recent_trades[user_id]).total_seconds()
    return elapsed <= CafeConfig.TRADE_TIMEOUT

async def _expire_trade_after(self, user_id: str, timeout: float) -> None:
    """지정된 시간 후 거래 기록 만료"""
    await asyncio.sleep(timeout)
    async with self._lock:
        if user_id in self.recent_trades:
            del self.recent_trades[user_id]
            await self._save_trade_records()

async def _save_trade_records(self) -> None:
    """거래 기록 저장"""
    data = {
        user_id: timestamp.isoformat()
        for user_id, timestamp in self.recent_trades.items()
    }
    await self.file_manager.save_trade_records(data)

async def cleanup_expired_trades(self) -> None:
    """만료된 거래 기록 정리"""
    current_time = datetime.now()
    expired_users = [
        user_id for user_id, timestamp in self.recent_trades.items()
        if (current_time - timestamp).total_seconds() > CafeConfig.TRADE_TIMEOUT
    ]
    
    for user_id in expired_users:
        del self.recent_trades[user_id]
    
    if expired_users:
        await self._save_trade_records()
        logger.debug(f"만료된 거래 기록 {len(expired_users)}개 정리")
```

# === 메인 시스템 ===

class CafeDiceSystem:
“”“카페 주사위 시스템 - 완전 재작성”””

```
def __init__(self, bot):
    self.bot = weakref.ref(bot)
    
    # 컴포넌트 초기화
    self.file_manager = DataFileManager()
    self.awakening_manager = AwakeningManager(self.file_manager)
    self.trade_tracker = TradeTracker(self.file_manager)
    
    # 상태 관리
    self.daily_dice_users: Set[str] = set()
    self.processing_messages: Set[int] = set()  # 중복 처리 방지
    
    # 백그라운드 작업
    self.cleanup_task: Optional[asyncio.Task] = None
    self._shutdown_event = asyncio.Event()
    
    logger.info("카페 주사위 시스템 초기화 완료")

async def initialize(self) -> None:
    """시스템 초기화"""
    try:
        # 컴포넌트 초기화
        await self.awakening_manager.initialize()
        await self.trade_tracker.initialize()
        
        # 일일 주사위 데이터 로드
        daily_data = await self.file_manager.load_daily_dice_data()
        self.daily_dice_users = set(daily_data.get('users', []))
        
        # 백그라운드 정리 작업 시작
        self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        logger.info(f"카페 시스템 초기화 완료 - 오늘 주사위: {len(self.daily_dice_users)}명")
        
    except Exception as e:
        logger.error(f"카페 시스템 초기화 실패: {e}")
        raise

async def handle_dice_message(self, message: discord.Message) -> bool:
    """주사위 메시지 처리"""
    # 기본 검증
    if not self._validate_message(message):
        return False
    
    # 중복 처리 방지
    if message.id in self.processing_messages:
        return False
    
    self.processing_messages.add(message.id)
    
    try:
        # 메시지 파싱
        parse_result = DiceMessageParser.parse_dice_message(message.content)
        if not parse_result:
            return False
        
        display_name, dice_value = parse_result
        logger.info(f"주사위 파싱: {display_name} -> {dice_value}")
        
        # 멤버 찾기
        member_data = await self._find_member_from_message(message, display_name)
        if not member_data:
            return False
        
        # 거래 확인 (필요시)
        user_id = str(member_data.discord_id)
        if not self.trade_tracker.has_recent_trade(user_id):
            logger.warning(f"{member_data.name} - 최근 거래 없음")
            # 거래 없이도 처리하려면 이 라인을 주석 처리
            # return False
        
        # 일일 제한 확인
        if user_id in self.daily_dice_users:
            logger.info(f"{member_data.name} - 오늘 이미 주사위 굴림")
            return False
        
        # 주사위 결과 처리
        success = await self._process_dice_result(member_data, dice_value, message)
        
        if success:
            # 일일 기록 추가
            self.daily_dice_users.add(user_id)
            await self.file_manager.save_daily_dice_data(self.daily_dice_users)
            
            # 거래 기록 제거
            if user_id in self.trade_tracker.recent_trades:
                del self.trade_tracker.recent_trades[user_id]
            
            logger.info(f"주사위 처리 완료: {member_data.name}")
        
        return success
        
    except Exception as e:
        logger.error(f"주사위 메시지 처리 실패: {e}")
        return False
    finally:
        self.processing_messages.discard(message.id)

def _validate_message(self, message: discord.Message) -> bool:
    """메시지 기본 검증"""
    if message.channel.id != CafeConfig.CAFE_CHANNEL_ID:
        return False
    
    if message.author.id != CafeConfig.DICE_BOT_ID:
        return False
    
    return True

async def _find_member_from_message(self, message: discord.Message, display_name: str) -> Optional[MemberData]:
    """메시지에서 멤버 정보 찾기"""
    # 하드코딩된 이름 추출
    member_name, parsed_health = MemberDatabase.extract_member_info(display_name)
    if not member_name:
        logger.error(f"하드코딩된 이름 없음: {display_name}")
        return None
    
    # Discord 멤버 찾기
    discord_member = MemberDatabase.find_discord_member(message.guild, member_name)
    if not discord_member:
        logger.error(f"Discord 멤버 없음: {member_name}")
        return None
    
    return MemberData(
        discord_id=discord_member.id,
        name=member_name,
        display_name=discord_member.display_name,
        current_health=parsed_health,
        has_awakening=self.awakening_manager.is_awakened(str(discord_member.id))
    )

async def _process_dice_result(self, member_data: MemberData, dice_value: int, 
                             message: discord.Message) -> bool:
    """주사위 결과 처리"""
    dice_range = DiceMessageParser.get_dice_range_type(dice_value)
    if not dice_range:
        logger.info(f"처리 없음 - 주사위값: {dice_value}")
        return True
    
    bot_instance = self.bot()
    if not bot_instance:
        return False
    
    discord_member = bot_instance.get_user(member_data.discord_id)
    if not discord_member:
        discord_member = message.guild.get_member(member_data.discord_id)
    
    if not discord_member:
        logger.error(f"Discord 멤버 객체 없음: {member_data.discord_id}")
        return False
    
    try:
        if dice_range == DiceRange.AWAKENING:
            return await self._handle_awakening(discord_member)
        elif dice_range == DiceRange.PERSONAL_DAMAGE:
            return await self._handle_personal_damage(discord_member, -30)
        elif dice_range == DiceRange.AREA_DAMAGE:
            return await self._handle_area_damage(message.channel, discord_member)
        
    except Exception as e:
        logger.error(f"주사위 결과 처리 실패: {e}")
        return False
    
    return True

async def _handle_awakening(self, member: discord.Member) -> bool:
    """각성 처리"""
    return await self.awakening_manager.apply_awakening(member)

async def _handle_personal_damage(self, member: discord.Member, damage: int) -> bool:
    """개인 데미지 처리"""
    current_health = HealthManager.extract_health_from_name(member.display_name)
    if current_health is None:
        logger.warning(f"{member.display_name} - 체력 찾을 수 없음")
        return False
    
    new_health = max(0, current_health + damage)  # damage는 음수
    logger.info(f"개인 데미지: {member.display_name} {current_health} -> {new_health}")
    
    return await HealthManager.update_member_health(member, new_health)

async def _handle_area_damage(self, channel: discord.TextChannel, dice_roller: discord.Member) -> bool:
    """범위 데미지 처리"""
    logger.info(f"범위 데미지 처리: {dice_roller.display_name}")
    
    # 5분간 메시지 수집
    five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
    affected_members = set()
    channel_taggers = set()
    
    try:
        async for msg in channel.history(after=five_minutes_ago, limit=100):
            if msg.author.bot:
                continue
            
            # 채널 태그 확인
            if re.search(r'<#\d+>', msg.content):
                channel_taggers.add(msg.author.id)
            
            affected_members.add(msg.author)
    
    except Exception as e:
        logger.error(f"메시지 수집 실패: {e}")
        return False
    
    # 대상 필터링 (채널 태그한 사람, 주사위 굴린 사람 제외)
    targets = [
        m for m in affected_members 
        if m.id not in channel_taggers and m.id != dice_roller.id
    ]
    
    logger.info(f"범위 데미지 대상: {len(targets)}명")
    
    # 각 대상에게 데미지 적용
    success_count = 0
    for member in targets:
        try:
            if await self._handle_personal_damage(member, -20):
                success_count += 1
            await asyncio.sleep(CafeConfig.HEALTH_UPDATE_DELAY)
        except Exception as e:
            logger.error(f"범위 데미지 실패 {member.display_name}: {e}")
    
    logger.info(f"범위 데미지 완료: {success_count}/{len(targets)}")
    return success_count > 0 or len(targets) == 0

async def handle_trade_to_admin(self, user_id: str, target_id: str, amount: int) -> None:
    """Admin 거래 처리"""
    if target_id == CafeConfig.ADMIN_ID and amount == 1:
        await self.trade_tracker.record_trade(user_id)

async def _periodic_cleanup(self) -> None:
    """주기적 정리 작업"""
    while not self._shutdown_event.is_set():
        try:
            await asyncio.sleep(CafeConfig.CLEANUP_INTERVAL)
            
            # 자정에 일일 데이터 초기화
            now = datetime.now()
            if now.hour == 0 and now.minute < 1:
                self.daily_dice_users.clear()
                await self.file_manager.save_daily_dice_data(self.daily_dice_users)
                logger.info("일일 주사위 데이터 초기화")
            
            # 컴포넌트 정리
            await self.awakening_manager.cleanup_expired_sessions()
            await self.trade_tracker.cleanup_expired_trades()
            
            # 처리 중 메시지 정리 (오래된 것들)
            if len(self.processing_messages) > 100:
                self.processing_messages.clear()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"주기적 정리 실패: {e}")

async def shutdown(self) -> None:
    """시스템 종료"""
    logger.info("카페 시스템 종료 시작")
    
    self._shutdown_event.set()
    
    # 백그라운드 작업 종료
    if self.cleanup_task and not self.cleanup_task.done():
        self.cleanup_task.cancel()
        try:
            await self.cleanup_task
        except asyncio.CancelledError:
            pass
    
    # 컴포넌트 종료
    await self.awakening_manager.shutdown()
    
    # 데이터 저장
    await self.file_manager.save_daily_dice_data(self.daily_dice_users)
    
    logger.info("카페 시스템 종료 완료")
```

# === 전역 인터페이스 ===

cafe_dice_system: Optional[CafeDiceSystem] = None

def init_cafe_system(bot) -> CafeDiceSystem:
“”“카페 시스템 초기화”””
global cafe_dice_system
logger.info(“카페 시스템 초기화 시작”)

```
cafe_dice_system = CafeDiceSystem(bot)

# 초기화는 비동기로 처리되어야 함
asyncio.create_task(cafe_dice_system.initialize())

return cafe_dice_system
```

def get_cafe_system() -> Optional[CafeDiceSystem]:
“”“카페 시스템 인스턴스 반환”””
return cafe_dice_system

async def handle_message(message: discord.Message) -> bool:
“”“메시지 처리 - 외부 인터페이스”””
system = get_cafe_system()
if not system:
return False

```
# 주사위 봇 메시지만 처리
if message.author.bot and message.author.id == CafeConfig.DICE_BOT_ID:
    return await system.handle_dice_message(message)

return False
```

async def handle_trade_to_admin(user_id: str, target_id: str, amount: int) -> None:
“”“Admin 거래 처리 - 외부 인터페이스”””
system = get_cafe_system()
if system:
await system.handle_trade_to_admin(user_id, target_id, amount)