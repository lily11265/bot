# BambooForest.py - 완전 재작성 버전

import asyncio
import json
import logging
import os
import re
import time
import weakref
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union
import aiofiles
import aiohttp
import discord
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.service_account import Credentials

logger = logging.getLogger(**name**)

# === 상수 정의 ===

SCOPES_DRIVE = [‘https://www.googleapis.com/auth/drive.file’]
BAMBOO_FOLDER_ID = ‘1OUDj9HcY_zZNeraxNOFl1PwVGBNmzfMN’
SPECIAL_USER_IDS = {“1007172975222603798”, “1090546247770832910”}

# 설정값

DEFAULT_RATE_LIMIT = 1.0
MAX_MESSAGE_PARTS = 20
MAX_IMAGE_SIZE = 8 * 1024 * 1024  # 8MB
SESSION_TIMEOUT = 1800  # 30분
CLEANUP_INTERVAL = 900  # 15분
MAX_RETRIES = 3

# 파일 경로

DATA_DIR = “bamboo_data”
MAPPINGS_FILE = os.path.join(DATA_DIR, “message_mappings.json”)
SESSIONS_FILE = os.path.join(DATA_DIR, “active_sessions.json”)

class MessageType(Enum):
“”“메시지 타입”””
TEXT = “text”
IMAGE = “image”

class SessionStatus(Enum):
“”“세션 상태”””
EDITING = “editing”
SENDING = “sending”
COMPLETED = “completed”
ERROR = “error”

@dataclass
class MessagePart:
“”“메시지 구성 요소”””
type: MessageType
content: str  # 텍스트 내용 또는 이미지 URL
order: int
original_url: Optional[str] = None  # 원본 Discord URL (이미지용)

```
def to_dict(self) -> Dict:
    """딕셔너리로 변환"""
    return {
        'type': self.type.value,
        'content': self.content,
        'order': self.order,
        'original_url': self.original_url
    }

@classmethod
def from_dict(cls, data: Dict) -> 'MessagePart':
    """딕셔너리에서 생성"""
    return cls(
        type=MessageType(data['type']),
        content=data['content'],
        order=data['order'],
        original_url=data.get('original_url')
    )
```

@dataclass
class AnonymousPost:
“”“익명 게시물”””
post_id: str
author_id: str
thread_id: int
message_ids: List[int] = field(default_factory=list)
parts: List[MessagePart] = field(default_factory=list)
created_at: datetime = field(default_factory=datetime.now)
edited: bool = False
edit_history: List[Dict] = field(default_factory=list)

```
def to_dict(self) -> Dict:
    """딕셔너리로 변환"""
    return {
        'post_id': self.post_id,
        'author_id': self.author_id,
        'thread_id': self.thread_id,
        'message_ids': self.message_ids,
        'parts': [part.to_dict() for part in self.parts],
        'created_at': self.created_at.isoformat(),
        'edited': self.edited,
        'edit_history': self.edit_history
    }

@classmethod
def from_dict(cls, data: Dict) -> 'AnonymousPost':
    """딕셔너리에서 생성"""
    parts = [MessagePart.from_dict(part_data) for part_data in data.get('parts', [])]
    return cls(
        post_id=data['post_id'],
        author_id=data['author_id'],
        thread_id=data['thread_id'],
        message_ids=data.get('message_ids', []),
        parts=parts,
        created_at=datetime.fromisoformat(data['created_at']),
        edited=data.get('edited', False),
        edit_history=data.get('edit_history', [])
    )
```

@dataclass
class BambooSession:
“”“대나무숲 세션”””
user_id: str
thread_id: int
status: SessionStatus
start_message_id: int
created_at: datetime = field(default_factory=datetime.now)
last_activity: datetime = field(default_factory=datetime.now)

```
def is_expired(self, timeout: int = SESSION_TIMEOUT) -> bool:
    """세션 만료 확인"""
    return (datetime.now() - self.last_activity).total_seconds() > timeout

def update_activity(self):
    """활동 시간 업데이트"""
    self.last_activity = datetime.now()

def to_dict(self) -> Dict:
    """딕셔너리로 변환"""
    return {
        'user_id': self.user_id,
        'thread_id': self.thread_id,
        'status': self.status.value,
        'start_message_id': self.start_message_id,
        'created_at': self.created_at.isoformat(),
        'last_activity': self.last_activity.isoformat()
    }

@classmethod
def from_dict(cls, data: Dict) -> 'BambooSession':
    """딕셔너리에서 생성"""
    return cls(
        user_id=data['user_id'],
        thread_id=data['thread_id'],
        status=SessionStatus(data['status']),
        start_message_id=data['start_message_id'],
        created_at=datetime.fromisoformat(data['created_at']),
        last_activity=datetime.fromisoformat(data['last_activity'])
    )
```

@dataclass
class EditSession:
“”“편집 세션”””
user_id: str
post_id: str
dm_channel_id: int
initial_message_id: int
created_at: datetime = field(default_factory=datetime.now)

```
def is_expired(self, timeout: int = SESSION_TIMEOUT) -> bool:
    """세션 만료 확인"""
    return (datetime.now() - self.created_at).total_seconds() > timeout
```

class RateLimiter:
“”“개선된 Rate Limiter”””

```
def __init__(self):
    self._delays: Dict[str, float] = {}
    self._last_requests: Dict[str, datetime] = {}
    self._lock = asyncio.Lock()

async def wait_if_needed(self, key: str, min_delay: float = DEFAULT_RATE_LIMIT):
    """필요시 대기"""
    async with self._lock:
        now = datetime.now()
        
        if key in self._last_requests:
            elapsed = (now - self._last_requests[key]).total_seconds()
            required_delay = self._delays.get(key, min_delay)
            
            if elapsed < required_delay:
                wait_time = required_delay - elapsed
                await asyncio.sleep(wait_time)
        
        self._last_requests[key] = datetime.now()

async def handle_rate_limit(self, key: str, retry_after: float):
    """Rate limit 처리"""
    async with self._lock:
        self._delays[key] = retry_after + 0.5
        logger.warning(f"Rate limit: {key} -> {retry_after}초 대기")
        await asyncio.sleep(retry_after + 0.5)

async def cleanup_old_entries(self):
    """오래된 항목 정리"""
    async with self._lock:
        cutoff = datetime.now() - timedelta(minutes=10)
        
        expired_keys = [
            key for key, timestamp in self._last_requests.items()
            if timestamp < cutoff
        ]
        
        for key in expired_keys:
            self._last_requests.pop(key, None)
            self._delays.pop(key, None)
```

class DriveUploader:
“”“구글 드라이브 업로더”””

```
def __init__(self):
    self.service = self._setup_drive_service()
    self._upload_lock = asyncio.Lock()
    self.upload_stats = {'success': 0, 'failure': 0}

def _setup_drive_service(self):
    """드라이브 서비스 설정"""
    try:
        if os.path.exists("service_account.json"):
            credentials = Credentials.from_service_account_file(
                "service_account.json", scopes=SCOPES_DRIVE
            )
            service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
            logger.info("구글 드라이브 서비스 초기화 성공")
            return service
    except Exception as e:
        logger.error(f"구글 드라이브 서비스 초기화 실패: {e}")
    return None

async def upload_image(self, image_data: bytes, filename: str) -> Optional[str]:
    """이미지 업로드"""
    if not self.service:
        logger.warning("드라이브 서비스 없음 - 로컬 저장으로 대체")
        return await self._save_local_fallback(image_data, filename)
    
    # 크기 제한 확인
    if len(image_data) > MAX_IMAGE_SIZE:
        logger.warning(f"이미지 크기 초과: {len(image_data)} bytes")
        return None
    
    temp_path = None
    try:
        async with self._upload_lock:
            # 임시 파일 생성
            temp_path = f"temp_{int(time.time())}_{filename}"
            
            # 비동기 파일 쓰기
            await self._write_temp_file(temp_path, image_data)
            
            # 드라이브 업로드
            url = await asyncio.get_event_loop().run_in_executor(
                None, self._upload_to_drive_sync, temp_path, filename
            )
            
            if url:
                self.upload_stats['success'] += 1
                logger.info(f"드라이브 업로드 성공: {filename}")
                return url
            else:
                self.upload_stats['failure'] += 1
                return await self._save_local_fallback(image_data, filename)
            
    except Exception as e:
        logger.error(f"드라이브 업로드 실패: {e}")
        self.upload_stats['failure'] += 1
        return await self._save_local_fallback(image_data, filename)
    finally:
        # 임시 파일 정리
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

async def _write_temp_file(self, path: str, data: bytes):
    """임시 파일 쓰기"""
    async with aiofiles.open(path, 'wb') as f:
        await f.write(data)

def _upload_to_drive_sync(self, temp_path: str, filename: str) -> Optional[str]:
    """동기 드라이브 업로드"""
    try:
        file_metadata = {
            'name': filename,
            'parents': [BAMBOO_FOLDER_ID]
        }
        
        media = MediaFileUpload(temp_path, resumable=True)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        # 공유 설정
        self.service.permissions().create(
            fileId=file.get('id'),
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        return f"https://drive.google.com/uc?export=view&id={file.get('id')}"
        
    except Exception as e:
        logger.error(f"동기 드라이브 업로드 실패: {e}")
        return None

async def _save_local_fallback(self, image_data: bytes, filename: str) -> str:
    """로컬 저장 폴백"""
    try:
        local_dir = os.path.join(DATA_DIR, "images")
        os.makedirs(local_dir, exist_ok=True)
        
        local_path = os.path.join(local_dir, filename)
        await self._write_temp_file(local_path, image_data)
        
        logger.info(f"로컬 저장 완료: {filename}")
        return f"file://{os.path.abspath(local_path)}"
        
    except Exception as e:
        logger.error(f"로컬 저장 실패: {e}")
        return None
```

class BambooForestSystem:
“”“대나무숲 시스템 - 완전 재작성”””

```
def __init__(self, bot):
    self.bot = weakref.ref(bot)
    
    # 핵심 컴포넌트
    self.rate_limiter = RateLimiter()
    self.drive_uploader = DriveUploader()
    
    # 데이터 저장소
    self.anonymous_posts: Dict[str, AnonymousPost] = {}
    self.message_to_post: Dict[int, str] = {}  # message_id -> post_id
    self.bamboo_sessions: Dict[Tuple[int, str], BambooSession] = {}  # (thread_id, user_id) -> session
    self.edit_sessions: Dict[str, EditSession] = {}  # user_id -> edit_session
    
    # HTTP 세션
    self.http_session: Optional[aiohttp.ClientSession] = None
    
    # 캐시
    self._bamboo_channel_cache: Optional[discord.TextChannel] = None
    self._channel_cache_time: Optional[datetime] = None
    
    # 백그라운드 작업
    self.cleanup_task: Optional[asyncio.Task] = None
    self.save_task: Optional[asyncio.Task] = None
    
    # 통계
    self.stats = {
        'posts_created': 0,
        'messages_sent': 0,
        'edits_completed': 0,
        'errors': 0
    }
    
    # 초기화
    self._ensure_data_dir()
    self._load_all_data()
    self._start_background_tasks()
    
    logger.info("대나무숲 시스템 초기화 완료")

def _ensure_data_dir(self):
    """데이터 디렉토리 생성"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(DATA_DIR, "images"), exist_ok=True)
    except Exception as e:
        logger.error(f"데이터 디렉토리 생성 실패: {e}")

def _load_all_data(self):
    """모든 데이터 로드"""
    try:
        self._load_mappings()
        self._load_sessions()
        logger.info("데이터 로드 완료")
    except Exception as e:
        logger.error(f"데이터 로드 실패: {e}")

def _load_mappings(self):
    """매핑 데이터 로드"""
    try:
        if not os.path.exists(MAPPINGS_FILE):
            return
        
        with open(MAPPINGS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for post_data in data.get('posts', []):
            try:
                post = AnonymousPost.from_dict(post_data)
                self.anonymous_posts[post.post_id] = post
                
                # 메시지 매핑 복원
                for msg_id in post.message_ids:
                    self.message_to_post[msg_id] = post.post_id
                    
            except Exception as e:
                logger.error(f"게시물 복원 실패: {e}")
        
        logger.info(f"매핑 데이터 로드: {len(self.anonymous_posts)}개 게시물")
        
    except Exception as e:
        logger.error(f"매핑 로드 실패: {e}")

def _load_sessions(self):
    """세션 데이터 로드"""
    try:
        if not os.path.exists(SESSIONS_FILE):
            return
        
        with open(SESSIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 대나무숲 세션 복원
        for session_data in data.get('bamboo_sessions', []):
            try:
                session = BambooSession.from_dict(session_data)
                if not session.is_expired():
                    key = (session.thread_id, session.user_id)
                    self.bamboo_sessions[key] = session
            except Exception as e:
                logger.error(f"세션 복원 실패: {e}")
        
        logger.info(f"세션 데이터 로드: {len(self.bamboo_sessions)}개 활성 세션")
        
    except Exception as e:
        logger.error(f"세션 로드 실패: {e}")

def _start_background_tasks(self):
    """백그라운드 작업 시작"""
    try:
        self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self.save_task = asyncio.create_task(self._periodic_save())
        logger.info("백그라운드 작업 시작됨")
    except Exception as e:
        logger.error(f"백그라운드 작업 시작 실패: {e}")

async def _periodic_cleanup(self):
    """주기적 정리"""
    while True:
        try:
            await asyncio.sleep(CLEANUP_INTERVAL)
            
            # 만료된 세션 정리
            await self._cleanup_expired_sessions()
            
            # Rate limiter 정리
            await self.rate_limiter.cleanup_old_entries()
            
            # HTTP 세션 상태 확인
            await self._check_http_session()
            
            # 통계 로깅
            total_ops = sum(self.stats.values())
            if total_ops > 0:
                logger.debug(f"대나무숲 통계: {self.stats}")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"정리 작업 실패: {e}")

async def _periodic_save(self):
    """주기적 저장"""
    while True:
        try:
            await asyncio.sleep(600)  # 10분마다
            await self._save_all_data()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"자동 저장 실패: {e}")

async def _cleanup_expired_sessions(self):
    """만료된 세션 정리"""
    try:
        # 대나무숲 세션 정리
        expired_bamboo = [
            key for key, session in self.bamboo_sessions.items()
            if session.is_expired()
        ]
        
        for key in expired_bamboo:
            del self.bamboo_sessions[key]
        
        # 편집 세션 정리
        expired_edit = [
            user_id for user_id, session in self.edit_sessions.items()
            if session.is_expired()
        ]
        
        for user_id in expired_edit:
            del self.edit_sessions[user_id]
        
        if expired_bamboo or expired_edit:
            logger.debug(f"만료된 세션 정리: 대나무숲 {len(expired_bamboo)}, 편집 {len(expired_edit)}")
            
    except Exception as e:
        logger.error(f"세션 정리 실패: {e}")

async def _check_http_session(self):
    """HTTP 세션 상태 확인"""
    try:
        if self.http_session and self.http_session.closed:
            self.http_session = None
            logger.info("HTTP 세션 재설정됨")
    except Exception as e:
        logger.error(f"HTTP 세션 확인 실패: {e}")

async def _get_http_session(self) -> aiohttp.ClientSession:
    """HTTP 세션 가져오기"""
    if self.http_session is None or self.http_session.closed:
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
        self.http_session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': 'BambooForest/2.0'}
        )
    return self.http_session

async def _save_all_data(self):
    """모든 데이터 저장"""
    try:
        await asyncio.gather(
            self._save_mappings(),
            self._save_sessions(),
            return_exceptions=True
        )
    except Exception as e:
        logger.error(f"데이터 저장 실패: {e}")

async def _save_mappings(self):
    """매핑 데이터 저장"""
    try:
        data = {
            'posts': [post.to_dict() for post in self.anonymous_posts.values()],
            'saved_at': datetime.now().isoformat()
        }
        
        # 임시 파일에 쓰고 원자적 이동
        temp_file = f"{MAPPINGS_FILE}.tmp"
        async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        
        # Windows에서도 작동하는 원자적 이동
        if os.path.exists(MAPPINGS_FILE):
            os.remove(MAPPINGS_FILE)
        os.rename(temp_file, MAPPINGS_FILE)
        
        logger.debug(f"매핑 데이터 저장: {len(self.anonymous_posts)}개")
        
    except Exception as e:
        logger.error(f"매핑 저장 실패: {e}")

async def _save_sessions(self):
    """세션 데이터 저장"""
    try:
        data = {
            'bamboo_sessions': [session.to_dict() for session in self.bamboo_sessions.values()],
            'saved_at': datetime.now().isoformat()
        }
        
        temp_file = f"{SESSIONS_FILE}.tmp"
        async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        
        if os.path.exists(SESSIONS_FILE):
            os.remove(SESSIONS_FILE)
        os.rename(temp_file, SESSIONS_FILE)
        
        logger.debug(f"세션 데이터 저장: {len(self.bamboo_sessions)}개")
        
    except Exception as e:
        logger.error(f"세션 저장 실패: {e}")

async def _find_bamboo_channel(self) -> Optional[discord.TextChannel]:
    """익명 게시판 채널 찾기"""
    try:
        # 캐시 확인 (5분간 유효)
        if (self._bamboo_channel_cache and self._channel_cache_time and
            (datetime.now() - self._channel_cache_time).total_seconds() < 300):
            return self._bamboo_channel_cache
        
        bot = self.bot()
        if not bot:
            return None
        
        for guild in bot.guilds:
            for channel in guild.text_channels:
                if channel.name == "익명-게시판":
                    self._bamboo_channel_cache = channel
                    self._channel_cache_time = datetime.now()
                    return channel
        
        return None
        
    except Exception as e:
        logger.error(f"채널 찾기 실패: {e}")
        return None

def _generate_post_id(self) -> str:
    """게시물 ID 생성"""
    return f"post_{int(time.time() * 1000)}"

def _is_special_user(self, user_id: str) -> bool:
    """특별 사용자 확인"""
    return user_id in SPECIAL_USER_IDS

def _validate_thread_for_bamboo(self, channel: discord.TextChannel) -> bool:
    """대나무숲 사용 가능한 스레드인지 확인"""
    return (channel.type == discord.ChannelType.private_thread and
            channel.parent and channel.parent.name == "일지")

async def start_bamboo_session(self, message: discord.Message) -> bool:
    """대나무숲 세션 시작"""
    try:
        user_id = str(message.author.id)
        
        # 특별 사용자는 어디서든 사용 가능
        if not self._is_special_user(user_id):
            if not self._validate_thread_for_bamboo(message.channel):
                return False
        
        session_key = (message.channel.id, user_id)
        
        # 기존 세션 확인
        if session_key in self.bamboo_sessions:
            existing_session = self.bamboo_sessions[session_key]
            if not existing_session.is_expired():
                existing_session.update_activity()
                await message.channel.send("이미 대나무숲 세션이 활성화되어 있습니다.")
                return True
        
        # 새 세션 생성
        session = BambooSession(
            user_id=user_id,
            thread_id=message.channel.id,
            status=SessionStatus.EDITING,
            start_message_id=message.id
        )
        
        self.bamboo_sessions[session_key] = session
        
        await message.channel.send(
            "🎋 **대나무숲 세션 시작**\n"
            "이 뒤의 메시지들이 익명-게시판으로 전송됩니다.\n"
            "자유롭게 작성하신 후 `!보내기`를 입력해주세요."
        )
        
        logger.info(f"대나무숲 세션 시작: {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"세션 시작 실패: {e}")
        self.stats['errors'] += 1
        return False

async def send_to_bamboo_forest(self, message: discord.Message) -> bool:
    """대나무숲으로 메시지 전송"""
    try:
        user_id = str(message.author.id)
        session_key = (message.channel.id, user_id)
        
        # 세션 확인
        if session_key not in self.bamboo_sessions:
            # 특별 사용자는 즉석 세션 생성
            if self._is_special_user(user_id):
                session = BambooSession(
                    user_id=user_id,
                    thread_id=message.channel.id,
                    status=SessionStatus.EDITING,
                    start_message_id=message.id - 1
                )
                self.bamboo_sessions[session_key] = session
            else:
                await message.channel.send("먼저 `!대나무숲` 명령어를 사용해주세요.")
                return False
        
        session = self.bamboo_sessions[session_key]
        
        if session.status != SessionStatus.EDITING:
            await message.channel.send("현재 세션 상태에서는 전송할 수 없습니다.")
            return False
        
        session.status = SessionStatus.SENDING
        session.update_activity()
        
        # Rate limit 적용
        await self.rate_limiter.wait_if_needed(f"bamboo_send_{user_id}")
        
        # 메시지 수집
        message_parts = await self._collect_message_parts(message, session.start_message_id)
        if not message_parts:
            await message.channel.send("전송할 메시지가 없습니다.")
            session.status = SessionStatus.ERROR
            return False
        
        # 익명 게시판 채널 찾기
        bamboo_channel = await self._find_bamboo_channel()
        if not bamboo_channel:
            await message.channel.send("익명-게시판 채널을 찾을 수 없습니다.")
            session.status = SessionStatus.ERROR
            return False
        
        # 메시지 전송
        sent_message_ids = await self._send_messages_to_channel(bamboo_channel, message_parts)
        
        if not sent_message_ids:
            await message.channel.send("메시지 전송에 실패했습니다.")
            session.status = SessionStatus.ERROR
            return False
        
        # 익명 게시물 생성
        post = AnonymousPost(
            post_id=self._generate_post_id(),
            author_id=user_id,
            thread_id=message.channel.id,
            message_ids=sent_message_ids,
            parts=message_parts
        )
        
        self.anonymous_posts[post.post_id] = post
        
        # 메시지 매핑 생성
        for msg_id in sent_message_ids:
            self.message_to_post[msg_id] = post.post_id
        
        # 세션 완료
        session.status = SessionStatus.COMPLETED
        del self.bamboo_sessions[session_key]
        
        self.stats['posts_created'] += 1
        self.stats['messages_sent'] += len(sent_message_ids)
        
        await message.channel.send("✅ 메시지가 익명-게시판에 전송되었습니다!")
        logger.info(f"대나무숲 전송 완료: {user_id} -> {len(sent_message_ids)}개 메시지")
        
        return True
        
    except Exception as e:
        logger.error(f"대나무숲 전송 실패: {e}")
        self.stats['errors'] += 1
        
        # 세션 상태 복구
        if session_key in self.bamboo_sessions:
            self.bamboo_sessions[session_key].status = SessionStatus.ERROR
        
        try:
            await message.channel.send("전송 중 오류가 발생했습니다.")
        except:
            pass
        
        return False

async def _collect_message_parts(self, end_message: discord.Message, start_message_id: int) -> List[MessagePart]:
    """메시지 부분들 수집"""
    try:
        parts = []
        order = 0
        
        # 메시지 수집 (제한된 수량)
        messages = []
        async for msg in end_message.channel.history(
            limit=MAX_MESSAGE_PARTS,
            after=discord.Object(id=start_message_id),
            before=end_message,
            oldest_first=True
        ):
            if (msg.author.id == end_message.author.id and 
                not msg.content.startswith("!") and
                msg.id != end_message.id):
                messages.append(msg)
        
        # 메시지 처리
        for msg in messages:
            # 텍스트 처리
            if msg.content:
                content = msg.content.strip()[:2000]  # Discord 제한
                if content:
                    parts.append(MessagePart(
                        type=MessageType.TEXT,
                        content=content,
                        order=order
                    ))
                    order += 1
            
            # 이미지 처리 (최대 5개)
            for attachment in msg.attachments[:5]:
                if (attachment.content_type and 
                    attachment.content_type.startswith('image/') and
                    attachment.size <= MAX_IMAGE_SIZE):
                    
                    # 이미지 다운로드 및 업로드
                    image_url = await self._process_image_attachment(attachment)
                    if image_url:
                        parts.append(MessagePart(
                            type=MessageType.IMAGE,
                            content=image_url,
                            order=order,
                            original_url=attachment.url
                        ))
                        order += 1
        
        return parts
        
    except Exception as e:
        logger.error(f"메시지 수집 실패: {e}")
        return []

async def _process_image_attachment(self, attachment: discord.Attachment) -> Optional[str]:
    """이미지 첨부파일 처리"""
    try:
        # 이미지 다운로드
        session = await self._get_http_session()
        async with session.get(attachment.url) as response:
            if response.status != 200:
                logger.error(f"이미지 다운로드 실패: {response.status}")
                return None
            
            image_data = await response.read()
        
        # 파일명 생성
        timestamp = int(time.time())
        filename = f"bamboo_{timestamp}_{attachment.filename}"
        
        # 드라이브 업로드
        return await self.drive_uploader.upload_image(image_data, filename)
        
    except Exception as e:
        logger.error(f"이미지 처리 실패: {e}")
        return None

async def _send_messages_to_channel(self, channel: discord.TextChannel, 
                                  parts: List[MessagePart]) -> List[int]:
    """채널에 메시지 전송"""
    sent_ids = []
    
    try:
        for part in parts:
            await self.rate_limiter.wait_if_needed(f"send_{channel.id}")
            
            try:
                if part.type == MessageType.TEXT:
                    # 텍스트 전송
                    msg = await channel.send(part.content)
                    sent_ids.append(msg.id)
                    
                elif part.type == MessageType.IMAGE:
                    # 이미지 전송 (임베드 사용)
                    embed = discord.Embed(color=0x2F3136)  # 다크 그레이
                    embed.set_image(url=part.content)
                    msg = await channel.send(embed=embed)
                    sent_ids.append(msg.id)
                
                await asyncio.sleep(0.5)  # 추가 지연
                
            except discord.HTTPException as e:
                if e.status == 429:  # Rate limit
                    await self.rate_limiter.handle_rate_limit(f"send_{channel.id}", e.retry_after)
                else:
                    logger.error(f"메시지 전송 실패: {e}")
                    break
            
    except Exception as e:
        logger.error(f"메시지 전송 실패: {e}")
    
    return sent_ids

async def handle_edit_reaction(self, payload, user: discord.User) -> bool:
    """편집 리액션 처리"""
    try:
        # 게시물 찾기
        post_id = self.message_to_post.get(payload.message_id)
        if not post_id or post_id not in self.anonymous_posts:
            return False
        
        post = self.anonymous_posts[post_id]
        
        # 권한 확인 (작성자이거나 특별 사용자)
        if post.author_id != str(user.id) and not self._is_special_user(str(user.id)):
            return False
        
        # 기존 편집 세션 확인
        if str(user.id) in self.edit_sessions:
            return False
        
        # 편집 안내 메시지 생성
        embed = discord.Embed(
            title="📝 익명 메시지 편집",
            description="수정할 내용을 다음 형식으로 입력해주세요:",
            color=discord.Color.gold()
        )
        
        # 현재 내용 표시 (간소화)
        content_preview = []
        for i, part in enumerate(post.parts[:5], 1):  # 최대 5개만 표시
            if part.type == MessageType.TEXT:
                preview = part.content[:50] + "..." if len(part.content) > 50 else part.content
                content_preview.append(f"**{i}.** [텍스트] {preview}")
            else:
                content_preview.append(f"**{i}.** [이미지]")
        
        embed.add_field(
            name="현재 내용",
            value="\n".join(content_preview) if content_preview else "없음",
            inline=False
        )
        
        embed.add_field(
            name="편집 방법",
            value="• 텍스트 수정: `1-새로운 내용`\n"
                  "• 이미지 수정: `2-` 다음에 새 이미지 첨부\n"
                  "• 완료: `!수정 끝`",
            inline=False
        )
        
        try:
            dm_channel = await user.create_dm()
            initial_msg = await dm_channel.send(embed=embed)
            
            # 편집 세션 생성
            self.edit_sessions[str(user.id)] = EditSession(
                user_id=str(user.id),
                post_id=post_id,
                dm_channel_id=dm_channel.id,
                initial_message_id=initial_msg.id
            )
            
            logger.info(f"편집 세션 시작: {user.id}")
            return True
            
        except discord.Forbidden:
            logger.error(f"DM 전송 실패: {user.id}")
            return False
            
    except Exception as e:
        logger.error(f"편집 리액션 처리 실패: {e}")
        return False

async def handle_restore_reaction(self, payload) -> bool:
    """복원 리액션 처리"""
    try:
        # 게시물 찾기
        post_id = self.message_to_post.get(payload.message_id)
        if not post_id or post_id not in self.anonymous_posts:
            return False
        
        post = self.anonymous_posts[post_id]
        
        # 편집된 게시물만 복원 가능
        if not post.edited or not post.edit_history:
            return False
        
        bot = self.bot()
        if not bot:
            return False
        
        channel = bot.get_channel(payload.channel_id)
        if not channel:
            return False
        
        # 원본 내용 찾기 (첫 번째 편집 이전)
        if not post.edit_history:
            return False
        
        # 원본 상태로 복원 (편집 이력에서 원본 찾기)
        original_parts = None
        for history_entry in reversed(post.edit_history):
            if 'original_parts' in history_entry:
                original_parts = [
                    MessagePart.from_dict(part_data) 
                    for part_data in history_entry['original_parts']
                ]
                break
        
        if not original_parts:
            return False
        
        # 메시지 복원
        restored_count = 0
        for i, (part, msg_id) in enumerate(zip(original_parts, post.message_ids)):
            if i >= len(post.message_ids):
                break
            
            try:
                msg = await channel.fetch_message(msg_id)
                
                if part.type == MessageType.TEXT:
                    await msg.edit(content=part.content)
                elif part.type == MessageType.IMAGE:
                    embed = discord.Embed(color=0x2F3136)
                    embed.set_image(url=part.content)
                    await msg.edit(embed=embed)
                
                restored_count += 1
                await asyncio.sleep(0.5)
                
            except discord.HTTPException as e:
                logger.error(f"메시지 복원 실패: {e}")
        
        # 상태 업데이트
        if restored_count > 0:
            post.parts = original_parts
            post.edited = False
            post.edit_history.append({
                'action': 'restore',
                'timestamp': datetime.now().isoformat(),
                'restored_count': restored_count
            })
            
            logger.info(f"메시지 복원 완료: {post_id}, {restored_count}개")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"복원 처리 실패: {e}")
        return False

async def handle_author_check_reaction(self, payload, user: discord.User) -> bool:
    """작성자 확인 리액션 처리"""
    try:
        # 게시물 찾기
        post_id = self.message_to_post.get(payload.message_id)
        if not post_id or post_id not in self.anonymous_posts:
            return False
        
        post = self.anonymous_posts[post_id]
        
        # 작성자 정보 찾기
        bot = self.bot()
        if not bot:
            return False
        
        author_info = "알 수 없음"
        
        try:
            author_id = int(post.author_id)
            for guild in bot.guilds:
                member = guild.get_member(author_id)
                if member:
                    author_info = f"**{member.display_name}** ({member.name}#{member.discriminator})"
                    break
            else:
                # 사용자를 찾을 수 없는 경우
                author_info = f"ID: {post.author_id} (서버에서 찾을 수 없음)"
        
        except (ValueError, TypeError):
            author_info = f"잘못된 사용자 ID: {post.author_id}"
        
        # DM으로 정보 전송
        try:
            dm_channel = await user.create_dm()
            embed = discord.Embed(
                title="🔍 작성자 정보",
                description=f"익명 메시지 작성자: {author_info}",
                color=discord.Color.blue(),
                timestamp=post.created_at
            )
            await dm_channel.send(embed=embed)
            return True
            
        except discord.Forbidden:
            logger.error(f"작성자 정보 DM 전송 실패: {user.id}")
            return False
            
    except Exception as e:
        logger.error(f"작성자 확인 실패: {e}")
        return False

async def handle_dm_edit_completion(self, message: discord.Message) -> bool:
    """DM 편집 완료 처리"""
    try:
        user_id = str(message.author.id)
        
        if user_id not in self.edit_sessions:
            return False
        
        session = self.edit_sessions[user_id]
        post = self.anonymous_posts.get(session.post_id)
        
        if not post:
            await message.channel.send("게시물을 찾을 수 없습니다.")
            del self.edit_sessions[user_id]
            return False
        
        # 편집 내용 수집
        edits = await self._collect_edit_commands(message, session)
        
        if not edits:
            await message.channel.send("수정할 내용이 없습니다. 형식: `번호-내용`")
            return False
        
        # 익명 게시판 채널 찾기
        bamboo_channel = await self._find_bamboo_channel()
        if not bamboo_channel:
            await message.channel.send("익명-게시판 채널을 찾을 수 없습니다.")
            del self.edit_sessions[user_id]
            return False
        
        # 원본 저장 (처음 편집 시에만)
        if not post.edited:
            original_parts_data = [part.to_dict() for part in post.parts]
            post.edit_history.append({
                'action': 'backup_original',
                'timestamp': datetime.now().isoformat(),
                'original_parts': original_parts_data
            })
        
        # 편집 적용
        applied_edits = await self._apply_edits(post, edits, bamboo_channel)
        
        if applied_edits:
            # 편집 기록 추가
            post.edited = True
            post.edit_history.append({
                'action': 'edit',
                'timestamp': datetime.now().isoformat(),
                'editor_id': user_id,
                'edits': applied_edits
            })
            
            self.stats['edits_completed'] += 1
            
            await message.channel.send(
                f"✅ 편집 완료! 수정된 항목: {', '.join(map(str, applied_edits.keys()))}번"
            )
            
            logger.info(f"편집 완료: {session.post_id}, {len(applied_edits)}개 항목")
        else:
            await message.channel.send("편집 적용에 실패했습니다.")
        
        # 세션 정리
        del self.edit_sessions[user_id]
        return True
        
    except Exception as e:
        logger.error(f"편집 완료 처리 실패: {e}")
        
        # 세션 정리
        if str(message.author.id) in self.edit_sessions:
            del self.edit_sessions[str(message.author.id)]
        
        try:
            await message.channel.send("편집 처리 중 오류가 발생했습니다.")
        except:
            pass
        
        return False

async def _collect_edit_commands(self, end_message: discord.Message, session: EditSession) -> Dict:
    """편집 명령어 수집"""
    edits = {}
    
    try:
        # 세션 시작 이후의 메시지들 수집
        async for msg in end_message.channel.history(
            after=datetime.now() - timedelta(minutes=30),  # 30분 이내
            limit=50
        ):
            if (msg.author == end_message.author and 
                msg.id != session.initial_message_id and
                msg.content != "!수정 끝"):
                
                # 편집 명령어 파싱: "번호-내용"
                if '-' in msg.content:
                    parts = msg.content.split('-', 1)
                    if len(parts) == 2 and parts[0].strip().isdigit():
                        num = int(parts[0].strip())
                        content = parts[1].strip()
                        
                        # 이미지 첨부 확인
                        if msg.attachments:
                            for attachment in msg.attachments:
                                if (attachment.content_type and 
                                    attachment.content_type.startswith('image/')):
                                    # 이미지 처리
                                    image_url = await self._process_image_attachment(attachment)
                                    if image_url:
                                        edits[num] = {
                                            'type': 'image',
                                            'content': image_url,
                                            'original_url': attachment.url
                                        }
                                    break
                        else:
                            # 텍스트 편집
                            if content:
                                edits[num] = {
                                    'type': 'text',
                                    'content': content[:2000]  # Discord 제한
                                }
        
        return edits
        
    except Exception as e:
        logger.error(f"편집 명령어 수집 실패: {e}")
        return {}

async def _apply_edits(self, post: AnonymousPost, edits: Dict, 
                      channel: discord.TextChannel) -> Dict:
    """편집 적용"""
    applied = {}
    
    try:
        for num, edit_data in edits.items():
            # 범위 확인
            if not 1 <= num <= len(post.parts):
                continue
            
            part_idx = num - 1
            msg_idx = min(part_idx, len(post.message_ids) - 1)
            
            if msg_idx < 0 or msg_idx >= len(post.message_ids):
                continue
            
            try:
                msg_id = post.message_ids[msg_idx]
                msg = await channel.fetch_message(msg_id)
                
                if edit_data['type'] == 'text':
                    # 텍스트 편집
                    await msg.edit(content=edit_data['content'])
                    
                    # 내부 데이터 업데이트
                    if part_idx < len(post.parts):
                        post.parts[part_idx].content = edit_data['content']
                        post.parts[part_idx].type = MessageType.TEXT
                    
                    applied[num] = edit_data
                    
                elif edit_data['type'] == 'image':
                    # 이미지 편집
                    embed = discord.Embed(color=0x2F3136)
                    embed.set_image(url=edit_data['content'])
                    await msg.edit(embed=embed)
                    
                    # 내부 데이터 업데이트
                    if part_idx < len(post.parts):
                        post.parts[part_idx].content = edit_data['content']
                        post.parts[part_idx].type = MessageType.IMAGE
                        post.parts[part_idx].original_url = edit_data.get('original_url')
                    
                    applied[num] = edit_data
                
                await asyncio.sleep(0.5)  # Rate limit 방지
                
            except discord.HTTPException as e:
                logger.error(f"메시지 편집 실패 ({num}번): {e}")
                continue
        
        return applied
        
    except Exception as e:
        logger.error(f"편집 적용 실패: {e}")
        return {}

def get_stats(self) -> Dict:
    """시스템 통계 반환"""
    return {
        'posts': len(self.anonymous_posts),
        'active_bamboo_sessions': len(self.bamboo_sessions),
        'active_edit_sessions': len(self.edit_sessions),
        'message_mappings': len(self.message_to_post),
        'upload_stats': self.drive_uploader.upload_stats,
        'operation_stats': self.stats.copy()
    }

async def cleanup_old_posts(self, days: int = 30) -> int:
    """오래된 게시물 정리"""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        old_posts = [
            post_id for post_id, post in self.anonymous_posts.items()
            if post.created_at < cutoff_date
        ]
        
        for post_id in old_posts:
            post = self.anonymous_posts[post_id]
            
            # 메시지 매핑 정리
            for msg_id in post.message_ids:
                self.message_to_post.pop(msg_id, None)
            
            # 게시물 삭제
            del self.anonymous_posts[post_id]
        
        logger.info(f"오래된 게시물 {len(old_posts)}개 정리됨 ({days}일 이상)")
        return len(old_posts)
        
    except Exception as e:
        logger.error(f"게시물 정리 실패: {e}")
        return 0

async def shutdown(self):
    """시스템 종료"""
    logger.info("대나무숲 시스템 종료 시작")
    
    try:
        # 백그라운드 작업 취소
        tasks_to_cancel = []
        
        if self.cleanup_task and not self.cleanup_task.done():
            tasks_to_cancel.append(self.cleanup_task)
        
        if self.save_task and not self.save_task.done():
            tasks_to_cancel.append(self.save_task)
        
        # 작업 취소
        for task in tasks_to_cancel:
            task.cancel()
        
        # 취소 완료 대기
        if tasks_to_cancel:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=5.0
                )
            except asyncio.TimeoutError:
                logger.warning("일부 백그라운드 작업 취소 타임아웃")
        
        # HTTP 세션 정리
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        
        # 최종 데이터 저장
        await self._save_all_data()
        
        # 통계 출력
        stats = self.get_stats()
        logger.info(f"대나무숲 시스템 종료 완료 - 통계: {stats}")
        
    except Exception as e:
        logger.error(f"시스템 종료 중 오류: {e}")
```

# === 전역 인스턴스 및 함수 ===

bamboo_forest_system: Optional[BambooForestSystem] = None

def get_bamboo_system() -> Optional[BambooForestSystem]:
“”“대나무숲 시스템 인스턴스 반환”””
return bamboo_forest_system

def init_bamboo_system(bot) -> BambooForestSystem:
“”“대나무숲 시스템 초기화”””
global bamboo_forest_system
logger.info(“대나무숲 시스템 초기화”)
bamboo_forest_system = BambooForestSystem(bot)
return bamboo_forest_system

async def handle_message(message: discord.Message) -> bool:
“”“메시지 처리 (외부 호출용)”””
try:
if message.author.bot:
return False

```
    system = get_bamboo_system()
    if not system:
        return False
    
    # DM 편집 완료 처리
    if isinstance(message.channel, discord.DMChannel):
        if message.content == "!수정 끝":
            return await system.handle_dm_edit_completion(message)
        return False
    
    # 대나무숲 명령어 처리
    if message.content.startswith("!대나무숲"):
        return await system.start_bamboo_session(message)
    elif message.content == "!보내기":
        return await system.send_to_bamboo_forest(message)
    
    return False
    
except Exception as e:
    logger.error(f"메시지 처리 실패: {e}")
    return False
```

async def handle_reaction(payload) -> bool:
“”“리액션 처리 (외부 호출용)”””
try:
# 봇 리액션 무시
if payload.user_id == payload.member.bot if payload.member else False:
return False

```
    # 특별 권한 확인
    if str(payload.user_id) not in SPECIAL_USER_IDS:
        return False
    
    system = get_bamboo_system()
    if not system:
        return False
    
    bot = system.bot()
    if not bot:
        return False
    
    # Rate limit 적용
    await system.rate_limiter.wait_if_needed(f"reaction_{payload.user_id}")
    
    try:
        user = await bot.fetch_user(payload.user_id)
        channel = bot.get_channel(payload.channel_id)
        
        if not user or not channel:
            return False
        
        # 리액션 제거
        try:
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction(payload.emoji, user)
        except discord.HTTPException:
            pass
        
        # 이모지별 처리
        emoji = str(payload.emoji)
        
        if emoji == "✏️":
            return await system.handle_edit_reaction(payload, user)
        elif emoji == "🔄":
            return await system.handle_restore_reaction(payload)
        elif emoji == "❓":
            return await system.handle_author_check_reaction(payload, user)
        
    except discord.HTTPException as e:
        if e.status == 429:
            await system.rate_limiter.handle_rate_limit(f"reaction_{payload.user_id}", e.retry_after)
        logger.error(f"리액션 처리 실패: {e}")
        
    return False
    
except Exception as e:
    logger.error(f"리액션 처리 실패: {e}")
    return False
```

# === 관리자 유틸리티 함수 ===

async def get_system_status() -> Dict:
“”“시스템 상태 조회”””
try:
system = get_bamboo_system()
if not system:
return {‘error’: ‘System not initialized’}

```
    return system.get_stats()
    
except Exception as e:
    logger.error(f"상태 조회 실패: {e}")
    return {'error': str(e)}
```

async def cleanup_old_data(days: int = 30) -> Dict:
“”“오래된 데이터 정리”””
try:
system = get_bamboo_system()
if not system:
return {‘error’: ‘System not initialized’}

```
    cleaned_posts = await system.cleanup_old_posts(days)
    
    return {
        'success': True,
        'cleaned_posts': cleaned_posts,
        'cleanup_date': datetime.now().isoformat()
    }
    
except Exception as e:
    logger.error(f"데이터 정리 실패: {e}")
    return {'error': str(e)}
```

async def force_save_data() -> bool:
“”“강제 데이터 저장”””
try:
system = get_bamboo_system()
if system:
await system._save_all_data()
return True
return False
except Exception as e:
logger.error(f”강제 저장 실패: {e}”)
return False