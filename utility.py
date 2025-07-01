# utility.py - 완전 재작성 버전

import asyncio
import hashlib
import json
import logging
import os
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from dataclasses import dataclass, field
from enum import Enum
import aiofiles
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(**name**)

# === 상수 정의 ===

SCOPES = [“https://www.googleapis.com/auth/spreadsheets”]
SPREADSHEET_URL_INVENTORY = “https://docs.google.com/spreadsheets/d/1XIO0XZUicfGaSh5R-GdmGWWVUBBMzDYG1MhXmdbFpEQ/edit?usp=sharing”
SPREADSHEET_URL_METADATA = “https://docs.google.com/spreadsheets/d/1hYJHRjVTwcmKoxSHINhKApVHmCSmqEVOP7SQpjj3Pwg/edit?usp=sharing”

# API 설정

API_RATE_LIMIT = 100  # 분당 호출 수
API_RATE_WINDOW = 60  # 초
BATCH_SIZE = 10
MAX_RETRIES = 3

# 캐시 설정

DEFAULT_CACHE_TTL = 3600  # 1시간
SHORT_CACHE_TTL = 300     # 5분
LONG_CACHE_TTL = 86400    # 24시간

# 파일 경로

DATA_DIR = “utility_data”
CACHE_BACKUP_FILE = os.path.join(DATA_DIR, “cache_backup.json”)

class CacheLevel(Enum):
“”“캐시 레벨”””
MEMORY = “memory”
PERSISTENT = “persistent”
DISTRIBUTED = “distributed”

class OperationResult(Enum):
“”“작업 결과”””
SUCCESS = “success”
FAILURE = “failure”
PARTIAL = “partial”
CACHED = “cached”

@dataclass
class CacheEntry:
“”“캐시 항목”””
key: str
value: Any
created_at: datetime
ttl: int
access_count: int = 0
last_access: datetime = field(default_factory=datetime.now)

```
def is_expired(self) -> bool:
    """만료 확인"""
    return (datetime.now() - self.created_at).total_seconds() > self.ttl

def update_access(self):
    """접근 정보 업데이트"""
    self.access_count += 1
    self.last_access = datetime.now()

def to_dict(self) -> Dict:
    """딕셔너리로 변환"""
    return {
        'key': self.key,
        'value': self.value,
        'created_at': self.created_at.isoformat(),
        'ttl': self.ttl,
        'access_count': self.access_count,
        'last_access': self.last_access.isoformat()
    }

@classmethod
def from_dict(cls, data: Dict) -> 'CacheEntry':
    """딕셔너리에서 생성"""
    return cls(
        key=data['key'],
        value=data['value'],
        created_at=datetime.fromisoformat(data['created_at']),
        ttl=data['ttl'],
        access_count=data.get('access_count', 0),
        last_access=datetime.fromisoformat(data.get('last_access', data['created_at']))
    )
```

@dataclass
class UserData:
“”“사용자 데이터”””
user_id: str
name: str
inventory_name: str
user_type: str
health: str = “100”
coins: int = 0
items: List[str] = field(default_factory=list)
outfits: List[str] = field(default_factory=list)
physical_status: List[str] = field(default_factory=list)
corruption: int = 0

```
def to_dict(self) -> Dict:
    """딕셔너리로 변환"""
    return {
        'user_id': self.user_id,
        'name': self.name,
        'inventory_name': self.inventory_name,
        'type': self.user_type,
        'health': self.health,
        'coins': self.coins,
        'items': self.items,
        'outfits': self.outfits,
        'physical_status': self.physical_status,
        'corruption': self.corruption
    }
```

class APIRateLimiter:
“”“개선된 API Rate Limiter”””

```
def __init__(self, max_calls: int = API_RATE_LIMIT, window: int = API_RATE_WINDOW):
    self.max_calls = max_calls
    self.window = window
    self.calls: List[float] = []
    self._lock = asyncio.Lock()
    self.stats = {'total_calls': 0, 'waits': 0, 'avg_wait_time': 0.0}

async def acquire(self) -> float:
    """API 호출 권한 획득"""
    async with self._lock:
        now = time.time()
        
        # 윈도우 밖의 오래된 호출 제거
        self.calls = [call_time for call_time in self.calls if now - call_time < self.window]
        
        if len(self.calls) >= self.max_calls:
            # 가장 오래된 호출이 윈도우를 벗어날 때까지 대기
            oldest_call = self.calls[0]
            wait_time = self.window - (now - oldest_call) + 0.1
            
            self.stats['waits'] += 1
            self.stats['avg_wait_time'] = (
                (self.stats['avg_wait_time'] * (self.stats['waits'] - 1) + wait_time) / 
                self.stats['waits']
            )
            
            logger.debug(f"API rate limit - {wait_time:.2f}초 대기")
            await asyncio.sleep(wait_time)
            
            # 대기 후 다시 정리
            now = time.time()
            self.calls = [call_time for call_time in self.calls if now - call_time < self.window]
        
        self.calls.append(now)
        self.stats['total_calls'] += 1
        return now

def get_stats(self) -> Dict:
    """통계 반환"""
    return self.stats.copy()
```

class InMemoryCache:
“”“고성능 인메모리 캐시”””

```
def __init__(self, max_size: int = 1000, cleanup_threshold: float = 0.8):
    self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
    self._max_size = max_size
    self._cleanup_threshold = cleanup_threshold
    self._lock = asyncio.Lock()
    
    # 통계
    self._stats = {
        'hits': 0,
        'misses': 0,
        'evictions': 0,
        'cleanups': 0
    }
    
    # 백그라운드 작업
    self._cleanup_task: Optional[asyncio.Task] = None
    self._backup_task: Optional[asyncio.Task] = None
    
    self._start_background_tasks()

def _start_background_tasks(self):
    """백그라운드 작업 시작"""
    try:
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        self._backup_task = asyncio.create_task(self._periodic_backup())
    except Exception as e:
        logger.error(f"백그라운드 작업 시작 실패: {e}")

async def _periodic_cleanup(self):
    """주기적 정리"""
    while True:
        try:
            await asyncio.sleep(900)  # 15분마다
            await self._cleanup_expired()
            
            # 크기 관리
            async with self._lock:
                if len(self._cache) > self._max_size * self._cleanup_threshold:
                    self._evict_lru()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"캐시 정리 실패: {e}")

async def _periodic_backup(self):
    """주기적 백업"""
    while True:
        try:
            await asyncio.sleep(3600)  # 1시간마다
            await self._backup_to_disk()
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"캐시 백업 실패: {e}")

async def get(self, key: str) -> Optional[Any]:
    """캐시에서 값 가져오기"""
    async with self._lock:
        entry = self._cache.get(key)
        if entry:
            if not entry.is_expired():
                entry.update_access()
                self._cache.move_to_end(key)  # LRU 업데이트
                self._stats['hits'] += 1
                return entry.value
            else:
                # 만료된 항목 제거
                del self._cache[key]
                self._stats['evictions'] += 1
        
        self._stats['misses'] += 1
        return None

async def set(self, key: str, value: Any, ex: int = DEFAULT_CACHE_TTL):
    """캐시에 값 설정"""
    async with self._lock:
        # 크기 제한 확인
        if len(self._cache) >= self._max_size:
            self._evict_lru()
        
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=datetime.now(),
            ttl=ex
        )
        
        self._cache[key] = entry
        self._cache.move_to_end(key)

async def delete(self, key: str) -> bool:
    """키 삭제"""
    async with self._lock:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

async def delete_pattern(self, pattern: str):
    """패턴 매칭 삭제"""
    async with self._lock:
        keys_to_delete = [k for k in self._cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self._cache[key]

async def _cleanup_expired(self):
    """만료된 항목 정리"""
    async with self._lock:
        expired_keys = [k for k, v in self._cache.items() if v.is_expired()]
        for key in expired_keys:
            del self._cache[key]
            self._stats['evictions'] += 1
        
        if expired_keys:
            self._stats['cleanups'] += 1
            logger.debug(f"만료된 캐시 {len(expired_keys)}개 정리")

def _evict_lru(self):
    """LRU 기반 제거"""
    if not self._cache:
        return
    
    # 가장 적게 사용된 항목들을 우선 제거
    sorted_items = sorted(
        self._cache.items(),
        key=lambda x: (x[1].access_count, x[1].last_access)
    )
    
    remove_count = max(1, len(self._cache) // 10)  # 최소 1개, 최대 10% 제거
    
    for key, _ in sorted_items[:remove_count]:
        if key in self._cache:
            del self._cache[key]
            self._stats['evictions'] += 1

async def _backup_to_disk(self):
    """디스크에 백업"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        
        async with self._lock:
            backup_data = {
                'entries': [entry.to_dict() for entry in self._cache.values()],
                'stats': self._stats.copy(),
                'backup_time': datetime.now().isoformat()
            }
        
        async with aiofiles.open(CACHE_BACKUP_FILE, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(backup_data, ensure_ascii=False, indent=2))
        
        logger.debug("캐시 백업 완료")
        
    except Exception as e:
        logger.error(f"캐시 백업 실패: {e}")

async def restore_from_disk(self):
    """디스크에서 복원"""
    try:
        if not os.path.exists(CACHE_BACKUP_FILE):
            return
        
        async with aiofiles.open(CACHE_BACKUP_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
            backup_data = json.loads(content)
        
        async with self._lock:
            for entry_data in backup_data.get('entries', []):
                try:
                    entry = CacheEntry.from_dict(entry_data)
                    if not entry.is_expired():
                        self._cache[entry.key] = entry
                except Exception as e:
                    logger.error(f"캐시 항목 복원 실패: {e}")
            
            # 통계 복원
            if 'stats' in backup_data:
                self._stats.update(backup_data['stats'])
        
        logger.info(f"캐시 복원 완료: {len(self._cache)}개 항목")
        
    except Exception as e:
        logger.error(f"캐시 복원 실패: {e}")

def get_stats(self) -> Dict:
    """캐시 통계 반환"""
    total_requests = self._stats['hits'] + self._stats['misses']
    hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
    
    return {
        'size': len(self._cache),
        'hit_rate': hit_rate,
        'total_hits': self._stats['hits'],
        'total_misses': self._stats['misses'],
        'total_evictions': self._stats['evictions'],
        'cleanup_cycles': self._stats['cleanups']
    }

async def shutdown(self):
    """캐시 시스템 종료"""
    try:
        # 백그라운드 작업 취소
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        
        if self._backup_task and not self._backup_task.done():
            self._backup_task.cancel()
        
        # 최종 백업
        await self._backup_to_disk()
        
        logger.info("캐시 시스템 종료 완료")
        
    except Exception as e:
        logger.error(f"캐시 종료 실패: {e}")
```

class GoogleSheetsClient:
“”“개선된 Google Sheets 클라이언트”””

```
def __init__(self):
    self._credentials: Optional[Credentials] = None
    self._client: Optional[gspread.Client] = None
    self._inventory_sheet = None
    self._metadata_sheet = None
    self._lock = asyncio.Lock()
    
    # 연결 관리
    self._last_refresh = 0
    self._refresh_interval = 3600  # 1시간
    self._connection_attempts = 0
    self._max_connection_attempts = 3
    
    # 통계
    self._stats = {
        'api_calls': 0,
        'successful_calls': 0,
        'failed_calls': 0,
        'cache_hits': 0
    }

async def _ensure_connection(self):
    """연결 확보"""
    async with self._lock:
        current_time = time.time()
        
        # 연결 갱신 필요 확인
        if current_time - self._last_refresh > self._refresh_interval:
            self._client = None
            self._inventory_sheet = None
            self._metadata_sheet = None
        
        if self._credentials is None:
            try:
                self._credentials = Credentials.from_service_account_file(
                    "service_account.json", scopes=SCOPES
                )
            except Exception as e:
                logger.error(f"인증 정보 로드 실패: {e}")
                raise
        
        if self._client is None:
            self._client = gspread.authorize(self._credentials)
            self._last_refresh = current_time
            self._connection_attempts = 0

async def get_sheets(self) -> Tuple[gspread.Worksheet, gspread.Worksheet]:
    """시트 가져오기"""
    await self._ensure_connection()
    
    try:
        if self._inventory_sheet is None:
            spreadsheet = self._client.open_by_url(SPREADSHEET_URL_INVENTORY)
            self._inventory_sheet = spreadsheet.worksheet("러너 시트")
        
        if self._metadata_sheet is None:
            spreadsheet = self._client.open_by_url(SPREADSHEET_URL_METADATA)
            self._metadata_sheet = spreadsheet.worksheet("메타데이터시트")
        
        return self._inventory_sheet, self._metadata_sheet
        
    except Exception as e:
        logger.error(f"시트 가져오기 실패: {e}")
        # 연결 초기화 후 재시도
        self._client = None
        self._inventory_sheet = None
        self._metadata_sheet = None
        
        self._connection_attempts += 1
        if self._connection_attempts < self._max_connection_attempts:
            await asyncio.sleep(2 ** self._connection_attempts)  # 백오프
            return await self.get_sheets()
        else:
            raise

async def batch_get(self, ranges: List[str]) -> Dict:
    """배치 데이터 가져오기"""
    try:
        await rate_limiter.acquire()
        inventory_sheet, metadata_sheet = await self.get_sheets()
        
        # 범위별로 시트 분리
        inventory_ranges = []
        metadata_ranges = []
        
        for range_name in ranges:
            if "러너 시트" in range_name or range_name.startswith("B14:"):
                inventory_ranges.append(range_name)
            else:
                metadata_ranges.append(range_name)
        
        results = {}
        
        # 인벤토리 시트 배치 요청
        if inventory_ranges:
            batch_result = inventory_sheet.spreadsheet.values_batch_get(
                ranges=inventory_ranges
            ).execute()
            
            for i, range_name in enumerate(inventory_ranges):
                results[range_name] = batch_result['valueRanges'][i].get('values', [])
        
        # 메타데이터 시트 배치 요청
        if metadata_ranges:
            batch_result = metadata_sheet.spreadsheet.values_batch_get(
                ranges=metadata_ranges
            ).execute()
            
            for i, range_name in enumerate(metadata_ranges):
                results[range_name] = batch_result['valueRanges'][i].get('values', [])
        
        self._stats['api_calls'] += 1
        self._stats['successful_calls'] += 1
        
        return results
        
    except Exception as e:
        self._stats['api_calls'] += 1
        self._stats['failed_calls'] += 1
        logger.error(f"배치 데이터 가져오기 실패: {e}")
        raise

async def batch_update(self, updates: List[Dict]) -> bool:
    """배치 업데이트"""
    try:
        await rate_limiter.acquire()
        inventory_sheet, _ = await self.get_sheets()
        
        # 업데이트 요청 준비
        batch_update_request = {
            'value_input_option': 'RAW',
            'data': updates
        }
        
        inventory_sheet.spreadsheet.values_batch_update(batch_update_request).execute()
        
        self._stats['api_calls'] += 1
        self._stats['successful_calls'] += 1
        
        return True
        
    except Exception as e:
        self._stats['api_calls'] += 1
        self._stats['failed_calls'] += 1
        logger.error(f"배치 업데이트 실패: {e}")
        return False

async def get_single_cell(self, sheet_name: str, cell: str) -> Optional[str]:
    """단일 셀 값 가져오기"""
    try:
        await rate_limiter.acquire()
        _, metadata_sheet = await self.get_sheets()
        
        value = metadata_sheet.acell(cell).value
        
        self._stats['api_calls'] += 1
        self._stats['successful_calls'] += 1
        
        return value
        
    except Exception as e:
        self._stats['api_calls'] += 1
        self._stats['failed_calls'] += 1
        logger.error(f"단일 셀 가져오기 실패: {e}")
        return None

def get_stats(self) -> Dict:
    """클라이언트 통계 반환"""
    return self._stats.copy()
```

# === 전역 인스턴스 ===

cache_manager = InMemoryCache()
rate_limiter = APIRateLimiter()
sheets_client = GoogleSheetsClient()

# === 핵심 함수들 ===

async def get_cached_metadata() -> Dict[str, UserData]:
“”“메타데이터 캐싱”””
cached_data = await cache_manager.get(“user_metadata”)
if cached_data:
# UserData 객체로 변환
return {
user_id: UserData(**data) if isinstance(data, dict) else data
for user_id, data in cached_data.items()
}

```
try:
    # 배치로 데이터 가져오기
    ranges = [
        "메타데이터시트!A3:D37",
        "러너 시트!B14:B48"
    ]
    
    batch_data = await sheets_client.batch_get(ranges)
    metadata_range = batch_data.get("메타데이터시트!A3:D37", [])
    inventory_names = batch_data.get("러너 시트!B14:B48", [])
    
    user_mapping = {}
    
    # 인벤토리 이름 매핑 생성
    inventory_name_dict = {
        i: row[0].strip() for i, row in enumerate(inventory_names) if row
    }
    
    # 메타데이터 처리
    for idx, row in enumerate(metadata_range):
        if len(row) < 4 or not row[1]:
            continue
        
        name = row[0].strip()
        user_id = row[1].strip()
        can_give = row[2].strip().upper() == 'Y' if len(row) > 2 else False
        can_revoke = row[3].strip().upper() == 'Y' if len(row) > 3 else False
        
        # 인벤토리 이름 매칭
        inventory_name = inventory_name_dict.get(idx, name)
        
        # 이름 불일치 처리
        if name != inventory_name and inventory_name:
            matching_idx = next(
                (i for i, inv_name in inventory_name_dict.items() if inv_name == name),
                None
            )
            if matching_idx is not None:
                inventory_name = name
        
        user_data = UserData(
            user_id=user_id,
            name=name,
            inventory_name=inventory_name,
            user_type="admin" if can_give and can_revoke else "user"
        )
        
        user_mapping[user_id] = user_data
    
    # 캐시에 저장 (딕셔너리 형태로)
    cache_data = {
        user_id: user_data.to_dict() for user_id, user_data in user_mapping.items()
    }
    await cache_manager.set("user_metadata", cache_data, ex=LONG_CACHE_TTL)
    
    logger.info(f"메타데이터 캐싱 완료: {len(user_mapping)}명")
    return user_mapping
    
except Exception as e:
    logger.error(f"메타데이터 캐싱 실패: {e}")
    return {}
```

async def get_admin_id() -> str:
“”“Admin ID 조회”””
cached_id = await cache_manager.get(“admin_id”)
if cached_id:
return cached_id

```
try:
    admin_id = await sheets_client.get_single_cell("메타데이터시트", "B2")
    if admin_id:
        await cache_manager.set("admin_id", admin_id, ex=LONG_CACHE_TTL)
    return admin_id or ""
except Exception as e:
    logger.error(f"Admin ID 조회 실패: {e}")
    return ""
```

async def get_batch_user_data(user_ids: Optional[List[str]] = None) -> Dict[str, Dict]:
“”“배치 사용자 데이터 조회”””
# 전체 데이터 캐시 확인
cache_key = “all_user_data”
if not user_ids:
cached_data = await cache_manager.get(cache_key)
if cached_data:
return cached_data

```
try:
    # 메타데이터 가져오기
    user_metadata = await get_cached_metadata()
    if not user_metadata:
        return {}
    
    # 인벤토리 데이터 가져오기
    ranges = ["러너 시트!B14:H48"]
    batch_data = await sheets_client.batch_get(ranges)
    inventory_data = batch_data.get("러너 시트!B14:H48", [])
    
    batch_user_data = {}
    
    # 데이터 처리
    for row_idx, row in enumerate(inventory_data):
        if not row or not row[0]:
            continue
        
        # 행 길이 보정
        while len(row) < 7:
            row.append("")
        
        target_name = str(row[0]).strip()
        
        # 메타데이터에서 사용자 찾기
        user_info = None
        for metadata in user_metadata.values():
            if metadata.inventory_name.strip() == target_name:
                user_info = metadata
                break
        
        if not user_info:
            continue
        
        user_id = user_info.user_id
        
        # 특정 사용자 필터링
        if user_ids and user_id not in user_ids:
            continue
        
        # 데이터 파싱
        try:
            corruption_value = int(str(row[6]).strip()) if row[6] and str(row[6]).strip() else 0
        except ValueError:
            corruption_value = 0
        
        user_data = {
            "user_id": user_id,
            "name": user_info.name,
            "inventory_name": target_name,
            "health": str(row[1]).strip() if row[1] else "100",
            "coins": int(row[2]) if row[2] and str(row[2]).isdigit() else 0,
            "physical_status": [
                s.strip() for s in str(row[3]).split(",") if s.strip()
            ] if row[3] else [],
            "items": [
                i.strip() for i in str(row[4]).split(",") if i.strip()
            ] if row[4] else [],
            "outfits": [
                o.strip() for o in str(row[5]).split(",") if o.strip()
            ] if row[5] else [],
            "corruption": corruption_value,
        }
        
        batch_user_data[user_id] = user_data
        
        # 개별 사용자 캐시
        await cache_manager.set(f"user_data:{user_id}", user_data, ex=SHORT_CACHE_TTL)
    
    # 전체 데이터 캐시 (짧은 시간)
    if not user_ids:
        await cache_manager.set(cache_key, batch_user_data, ex=SHORT_CACHE_TTL)
    
    logger.debug(f"배치 사용자 데이터 조회 완료: {len(batch_user_data)}명")
    return batch_user_data
    
except Exception as e:
    logger.error(f"배치 사용자 데이터 조회 실패: {e}")
    return {}
```

async def get_user_inventory(user_id: str) -> Optional[Dict]:
“”“특정 사용자 인벤토리 조회”””
# 개별 캐시 확인
cached_data = await cache_manager.get(f”user_data:{user_id}”)
if cached_data:
return cached_data

```
# 배치 조회
user_data = await get_batch_user_data(user_ids=[user_id])
return user_data.get(user_id)
```

async def update_user_inventory(user_id: str, coins: Optional[int] = None,
items: Optional[List[str]] = None,
outfits: Optional[List[str]] = None,
physical_status: Optional[List[str]] = None,
corruption: Optional[int] = None,
health: Optional[str] = None) -> bool:
“”“사용자 인벤토리 업데이트”””
try:
# 메타데이터에서 사용자 찾기
user_metadata = await get_cached_metadata()
if user_id not in user_metadata:
logger.error(f”사용자 메타데이터 없음: {user_id}”)
return False

```
    target_name = user_metadata[user_id].inventory_name
    
    # 현재 데이터 가져오기
    ranges = ["러너 시트!B14:H48"]
    batch_data = await sheets_client.batch_get(ranges)
    inventory_data = batch_data.get("러너 시트!B14:H48", [])
    
    # 업데이트할 행 찾기
    target_row_idx = None
    for idx, row in enumerate(inventory_data):
        if row and str(row[0]).strip() == target_name:
            target_row_idx = idx
            break
    
    if target_row_idx is None:
        logger.error(f"인벤토리에서 사용자 없음: {target_name}")
        return False
    
    # 행 데이터 업데이트
    row = inventory_data[target_row_idx]
    while len(row) < 7:
        row.append("")
    
    updated = False
    
    if health is not None:
        row[1] = str(health)
        updated = True
    if coins is not None:
        row[2] = str(coins)
        updated = True
    if physical_status is not None:
        row[3] = ",".join(physical_status)
        updated = True
    if items is not None:
        row[4] = ",".join(items)
        updated = True
    if outfits is not None:
        row[5] = ",".join(outfits)
        updated = True
    if corruption is not None:
        row[6] = str(max(0, corruption))
        updated = True
    
    if not updated:
        return True
    
    # 시트 업데이트
    range_name = f"러너 시트!B{14 + target_row_idx}:H{14 + target_row_idx}"
    update_data = {
        'range': range_name,
        'values': [row]
    }
    
    success = await sheets_client.batch_update([update_data])
    
    if success:
        # 캐시 무효화
        await cache_manager.delete(f"user_data:{user_id}")
        await cache_manager.delete("all_user_data")
        await cache_manager.delete_pattern(f"user_inventory_display:{user_id}")
        
        logger.debug(f"사용자 인벤토리 업데이트 성공: {user_id}")
    
    return success
    
except Exception as e:
    logger.error(f"인벤토리 업데이트 실패: {e}")
    return False
```

async def batch_update_user_inventory(updates: Dict[str, Dict]) -> bool:
“”“배치 인벤토리 업데이트”””
if not updates:
return True

```
try:
    # 메타데이터 가져오기
    metadata = await get_cached_metadata()
    
    # 현재 데이터 가져오기
    ranges = ["러너 시트!B14:H48"]
    batch_data = await sheets_client.batch_get(ranges)
    inventory_data = batch_data.get("러너 시트!B14:H48", [])
    
    # 업데이트할 행 매핑
    update_mapping = {}
    for user_id in updates.keys():
        if user_id not in metadata:
            continue
        
        target_name = metadata[user_id].inventory_name
        for idx, row in enumerate(inventory_data):
            if row and str(row[0]).strip() == target_name:
                update_mapping[user_id] = idx
                break
    
    # 배치 업데이트 데이터 준비
    batch_updates = []
    updated_users = set()
    
    for user_id, update_data in updates.items():
        if user_id not in update_mapping:
            continue
        
        row_idx = update_mapping[user_id]
        row = inventory_data[row_idx].copy()
        
        # 행 길이 보정
        while len(row) < 7:
            row.append("")
        
        # 업데이트 적용
        if "health" in update_data:
            row[1] = str(update_data["health"])
        if "coins" in update_data:
            row[2] = str(update_data["coins"])
        if "physical_status" in update_data:
            row[3] = ",".join(update_data["physical_status"])
        if "items" in update_data:
            row[4] = ",".join(update_data["items"])
        if "outfits" in update_data:
            row[5] = ",".join(update_data["outfits"])
        if "corruption" in update_data:
            row[6] = str(max(0, update_data["corruption"]))
        
        # 업데이트 데이터 추가
        range_name = f"러너 시트!B{14 + row_idx}:H{14 + row_idx}"
        batch_updates.append({
            'range': range_name,
            'values': [row]
        })
        
        updated_users.add(user_id)
    
    if not batch_updates:
        return True
    
    # 배치 업데이트 실행
    success = await sheets_client.batch_update(batch_updates)
    
    if success:
        # 캐시 무효화
        cache_tasks = []
        for user_id in updated_users:
            cache_tasks.append(cache_manager.delete(f"user_data:{user_id}"))
            cache_tasks.append(cache_manager.delete(f"user_inventory_display:{user_id}"))
        
        cache_tasks.append(cache_manager.delete("all_user_data"))
        
        await asyncio.gather(*cache_tasks, return_exceptions=True)
        
        logger.info(f"배치 인벤토리 업데이트 완료: {len(updated_users)}명")
    
    return success
    
except Exception as e:
    logger.error(f"배치 인벤토리 업데이트 실패: {e}")
    return False
```

async def get_user_permissions(user_id: str) -> Tuple[bool, bool]:
“”“사용자 권한 확인”””
# 캐시 확인
cached_perms = await cache_manager.get(f”user_perms:{user_id}”)
if cached_perms:
return cached_perms.get(‘can_give’, False), cached_perms.get(‘can_revoke’, False)

```
try:
    # Admin 확인
    admin_id = await get_admin_id()
    if user_id == admin_id:
        perms = {'can_give': True, 'can_revoke': True}
        await cache_manager.set(f"user_perms:{user_id}", perms, ex=DEFAULT_CACHE_TTL)
        return True, True
    
    # 메타데이터에서 권한 확인
    ranges = ["메타데이터시트!A3:D37"]
    batch_data = await sheets_client.batch_get(ranges)
    metadata_range = batch_data.get("메타데이터시트!A3:D37", [])
    
    for row in metadata_range:
        if len(row) >= 4 and str(row[1]).strip() == user_id:
            can_give = str(row[2]).strip().upper() == 'Y'
            can_revoke = str(row[3]).strip().upper() == 'Y'
            
            perms = {'can_give': can_give, 'can_revoke': can_revoke}
            await cache_manager.set(f"user_perms:{user_id}", perms, ex=DEFAULT_CACHE_TTL)
            
            return can_give, can_revoke
    
    # 권한 없음
    perms = {'can_give': False, 'can_revoke': False}
    await cache_manager.set(f"user_perms:{user_id}", perms, ex=DEFAULT_CACHE_TTL)
    return False, False
    
except Exception as e:
    logger.error(f"권한 확인 실패: {e}")
    return False, False
```

def is_user_dead(user_inventory: Dict) -> bool:
“”“사용자 사망 상태 확인”””
if not user_inventory or “items” not in user_inventory:
return False
return “-사망-” in user_inventory[“items”]

async def increment_daily_values():
“”“일일 코인 증가”””
try:
logger.info(“일일 코인 증가 시작”)

```
    # 현재 데이터 가져오기
    ranges = ["러너 시트!B14:H48"]
    batch_data = await sheets_client.batch_get(ranges)
    inventory_data = batch_data.get("러너 시트!B14:H48", [])
    
    # 업데이트할 행들 준비
    batch_updates = []
    update_count = 0
    
    for row_idx, row in enumerate(inventory_data):
        if len(row) < 5:
            continue
        
        # 행 길이 보정
        while len(row) < 7:
            row.append("")
        
        # 아이템 확인
        items = str(row[4]).split(",") if row[4] else []
        
        # 사망자가 아니고 코인이 있는 경우만 증가
        if "-사망-" not in items and row[2] and str(row[2]).isdigit():
            current_coins = int(row[2])
            new_coins = current_coins + 1
            row[2] = str(new_coins)
            
            # 업데이트 데이터 추가
            range_name = f"러너 시트!B{14 + row_idx}:H{14 + row_idx}"
            batch_updates.append({
                'range': range_name,
                'values': [row]
            })
            
            update_count += 1
    
    # 배치 업데이트 실행
    if batch_updates:
        success = await sheets_client.batch_update(batch_updates)
        if success:
            # 모든 사용자 캐시 무효화
            await cache_manager.delete("all_user_data")
            await cache_manager.delete_pattern("user_data:")
            await cache_manager.delete_pattern("user_inventory_display:")
            
            logger.info(f"일일 코인 증가 완료: {update_count}명")
        else:
            logger.error("일일 코인 증가 실패")
    else:
        logger.info("일일 코인 증가: 대상자 없음")
    
except Exception as e:
    logger.error(f"일일 코인 증가 실패: {e}")
```

async def cache_daily_metadata():
“”“일일 메타데이터 캐싱”””
try:
logger.info(“일일 메타데이터 캐싱 시작”)

```
    # 기존 캐시 정리
    await cache_manager.delete_pattern("user_")
    await cache_manager.delete("admin_id")
    await cache_manager.delete("all_user_data")
    
    # 새로운 메타데이터 캐싱
    await get_cached_metadata()
    await get_admin_id()
    
    # 캐시 통계
    cache_stats = cache_manager.get_stats()
    sheets_stats = sheets_client.get_stats()
    rate_stats = rate_limiter.get_stats()
    
    logger.info(
        f"일일 메타데이터 캐싱 완료 - "
        f"캐시: {cache_stats['size']}개 항목, "
        f"API 호출: {sheets_stats['successful_calls']}회 성공, "
        f"Rate limit: 평균 대기 {rate_stats['avg_wait_time']:.2f}초"
    )
    
except Exception as e:
    logger.error(f"일일 메타데이터 캐싱 실패: {e}")
```

# === 유틸리티 함수들 ===

def calculate_corruption_change(current_value: int, change: int) -> int:
“”“타락도 변경 계산”””
return max(0, current_value + change)

def validate_corruption_input(input_str: str) -> Tuple[bool, int]:
“”“타락도 입력 유효성 검사”””
try:
value = int(input_str)
return True, value
except (ValueError, TypeError):
return False, 0

def calculate_data_hash(data: Union[Dict, List]) -> str:
“”“데이터 해시 계산”””
try:
json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
return hashlib.md5(json_str.encode(‘utf-8’)).hexdigest()
except Exception as e:
logger.error(f”해시 계산 실패: {e}”)
return “”

# === 시스템 관리 함수들 ===

async def get_system_stats() -> Dict:
“”“시스템 통계 조회”””
try:
cache_stats = cache_manager.get_stats()
sheets_stats = sheets_client.get_stats()
rate_stats = rate_limiter.get_stats()

```
    return {
        'cache': cache_stats,
        'sheets_api': sheets_stats,
        'rate_limiter': rate_stats,
        'timestamp': datetime.now().isoformat()
    }
except Exception as e:
    logger.error(f"시스템 통계 조회 실패: {e}")
    return {'error': str(e)}
```

async def cleanup_expired_cache():
“”“만료된 캐시 정리”””
try:
await cache_manager._cleanup_expired()
stats = cache_manager.get_stats()
logger.info(f”캐시 정리 완료 - 현재 {stats[‘size’]}개 항목”)
return True
except Exception as e:
logger.error(f”캐시 정리 실패: {e}”)
return False

async def force_refresh_metadata():
“”“메타데이터 강제 갱신”””
try:
await cache_manager.delete(“user_metadata”)
await cache_manager.delete(“admin_id”)

```
    metadata = await get_cached_metadata()
    admin_id = await get_admin_id()
    
    logger.info(f"메타데이터 강제 갱신 완료: {len(metadata)}명, Admin: {admin_id}")
    return True
except Exception as e:
    logger.error(f"메타데이터 강제 갱신 실패: {e}")
    return False
```

async def shutdown_utility_system():
“”“유틸리티 시스템 종료”””
try:
logger.info(“유틸리티 시스템 종료 시작”)

```
    # 캐시 시스템 종료
    await cache_manager.shutdown()
    
    # 최종 통계 출력
    stats = await get_system_stats()
    logger.info(f"유틸리티 시스템 종료 완료 - 최종 통계: {stats}")
    
except Exception as e:
    logger.error(f"유틸리티 시스템 종료 실패: {e}")
```

# === 초기화 ===

async def initialize_utility_system():
“”“유틸리티 시스템 초기화”””
try:
logger.info(“유틸리티 시스템 초기화 시작”)

```
    # 캐시 복원
    await cache_manager.restore_from_disk()
    
    # 초기 메타데이터 로드
    await get_cached_metadata()
    await get_admin_id()
    
    logger.info("유틸리티 시스템 초기화 완료")
    
except Exception as e:
    logger.error(f"유틸리티 시스템 초기화 실패: {e}")
    raise
```