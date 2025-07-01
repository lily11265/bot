# shop.py - 완전 재작성 버전

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union
import discord
from discord import app_commands

from utility import (
get_user_inventory, get_batch_user_data, update_user_inventory,
batch_update_user_inventory, get_user_permissions, is_user_dead,
cache_manager, calculate_corruption_change, validate_corruption_input,
get_admin_id
)

logger = logging.getLogger(**name**)

# === 상수 정의 ===

CAFE_CHANNEL_ID = 1388391607983800382
MAX_AUTOCOMPLETE_ITEMS = 25
CACHE_TIMEOUT = 300  # 5분
BATCH_OPERATION_TIMEOUT = 30  # 30초

class ItemType(Enum):
“”“아이템 유형”””
COIN = “코인”
ITEM = “아이템”
OUTFIT = “복장”
PHYSICAL_STATUS = “신체현황”
CORRUPTION = “타락도”
MONEY = “돈”  # 거래용 별칭

class OperationType(Enum):
“”“작업 유형”””
GIVE = “give”
REVOKE = “revoke”
TRADE = “trade”

@dataclass
class InventoryItem:
“”“인벤토리 아이템”””
name: str
item_type: ItemType
quantity: int = 1
metadata: Dict = field(default_factory=dict)

@dataclass
class OperationResult:
“”“작업 결과”””
success: bool
message: str
affected_users: List[str] = field(default_factory=list)
error_details: Optional[str] = None

@dataclass
class UserInventoryCache:
“”“사용자 인벤토리 캐시”””
user_id: str
data: Dict
last_updated: datetime

```
def is_expired(self, timeout: int = CACHE_TIMEOUT) -> bool:
    """캐시 만료 확인"""
    return (datetime.now() - self.last_updated).total_seconds() > timeout
```

class InventoryValidator:
“”“인벤토리 검증 클래스”””

```
@staticmethod
def validate_item_name(name: str) -> bool:
    """아이템 이름 유효성 검사"""
    if not name or not isinstance(name, str):
        return False
    
    # 길이 제한 (1-100자)
    if not 1 <= len(name.strip()) <= 100:
        return False
    
    # 특수 문자 제한
    forbidden_chars = ['<', '>', '&', '"', "'", '\\']
    return not any(char in name for char in forbidden_chars)

@staticmethod
def validate_coin_amount(amount_str: str) -> Tuple[bool, int]:
    """코인 양 검증"""
    try:
        amount = int(amount_str)
        # 음수 방지, 최대값 제한
        if 0 <= amount <= 999999999:
            return True, amount
        return False, 0
    except (ValueError, TypeError):
        return False, 0

@staticmethod
def validate_corruption_value(value_str: str) -> Tuple[bool, int]:
    """타락도 값 검증"""
    return validate_corruption_input(value_str)

@staticmethod
def validate_user_inventory(inventory: Dict) -> bool:
    """사용자 인벤토리 구조 검증"""
    required_fields = ['coins', 'items', 'outfits', 'physical_status', 'corruption']
    
    if not isinstance(inventory, dict):
        return False
    
    for field in required_fields:
        if field not in inventory:
            return False
    
    # 타입 검증
    if not isinstance(inventory['coins'], int):
        return False
    
    for field in ['items', 'outfits', 'physical_status']:
        if not isinstance(inventory[field], list):
            return False
    
    if not isinstance(inventory['corruption'], int):
        return False
    
    return True
```

class AsyncCacheManager:
“”“비동기 캐시 매니저”””

```
def __init__(self, max_size: int = 500):
    self.cache: Dict[str, UserInventoryCache] = {}
    self.max_size = max_size
    self._lock = asyncio.Lock()

async def get(self, user_id: str) -> Optional[Dict]:
    """캐시에서 인벤토리 가져오기"""
    async with self._lock:
        if user_id in self.cache:
            cached = self.cache[user_id]
            if not cached.is_expired():
                return cached.data
            else:
                # 만료된 캐시 제거
                del self.cache[user_id]
    return None

async def set(self, user_id: str, data: Dict):
    """캐시에 인벤토리 저장"""
    async with self._lock:
        # 캐시 크기 제한
        if len(self.cache) >= self.max_size:
            # 가장 오래된 항목 제거
            oldest_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].last_updated
            )
            del self.cache[oldest_key]
        
        self.cache[user_id] = UserInventoryCache(
            user_id=user_id,
            data=data.copy(),
            last_updated=datetime.now()
        )

async def invalidate(self, user_id: str):
    """특정 사용자 캐시 무효화"""
    async with self._lock:
        if user_id in self.cache:
            del self.cache[user_id]

async def invalidate_all(self):
    """모든 캐시 무효화"""
    async with self._lock:
        self.cache.clear()

async def cleanup_expired(self):
    """만료된 캐시 정리"""
    async with self._lock:
        expired_keys = [
            user_id for user_id, cached in self.cache.items()
            if cached.is_expired()
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"만료된 캐시 {len(expired_keys)}개 정리됨")
```

class InventoryManager:
“”“인벤토리 관리 클래스 - 완전 재작성”””

```
def __init__(self):
    self.validator = InventoryValidator()
    self.local_cache = AsyncCacheManager(max_size=300)
    self.operation_locks: Dict[str, asyncio.Lock] = {}
    self.batch_locks: Dict[str, asyncio.Lock] = {}
    
    # 성능 통계
    self.stats = {
        'operations': 0,
        'cache_hits': 0,
        'cache_misses': 0,
        'errors': 0
    }
    
    # 백그라운드 작업
    self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
    
    logger.info("인벤토리 매니저 초기화 완료")

async def _periodic_cleanup(self):
    """주기적 정리 작업"""
    while True:
        try:
            await asyncio.sleep(600)  # 10분마다
            
            # 캐시 정리
            await self.local_cache.cleanup_expired()
            
            # 사용하지 않는 락 정리
            await self._cleanup_unused_locks()
            
            # 통계 로깅
            if self.stats['operations'] > 0:
                hit_rate = (self.stats['cache_hits'] / 
                          (self.stats['cache_hits'] + self.stats['cache_misses'])) * 100
                logger.debug(f"인벤토리 통계 - 작업: {self.stats['operations']}, "
                           f"캐시 히트율: {hit_rate:.1f}%, 오류: {self.stats['errors']}")
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"정리 작업 실패: {e}")

async def _cleanup_unused_locks(self):
    """사용하지 않는 락 정리"""
    try:
        # 최대 100개 락만 유지
        if len(self.operation_locks) > 100:
            # 오래된 락들 제거 (간단히 절반 제거)
            keys_to_remove = list(self.operation_locks.keys())[:50]
            for key in keys_to_remove:
                if not self.operation_locks[key].locked():
                    del self.operation_locks[key]
        
        if len(self.batch_locks) > 50:
            keys_to_remove = list(self.batch_locks.keys())[:25]
            for key in keys_to_remove:
                if not self.batch_locks[key].locked():
                    del self.batch_locks[key]
    
    except Exception as e:
        logger.error(f"락 정리 실패: {e}")

async def _get_operation_lock(self, user_id: str) -> asyncio.Lock:
    """사용자별 작업 락 가져오기"""
    if user_id not in self.operation_locks:
        self.operation_locks[user_id] = asyncio.Lock()
    return self.operation_locks[user_id]

async def _get_batch_lock(self, operation_key: str) -> asyncio.Lock:
    """배치 작업 락 가져오기"""
    if operation_key not in self.batch_locks:
        self.batch_locks[operation_key] = asyncio.Lock()
    return self.batch_locks[operation_key]

async def get_cached_inventory(self, user_id: str) -> Optional[Dict]:
    """캐시된 사용자 인벤토리 조회"""
    try:
        # 로컬 캐시 확인
        cached_data = await self.local_cache.get(user_id)
        if cached_data:
            self.stats['cache_hits'] += 1
            return cached_data
        
        self.stats['cache_misses'] += 1
        
        # 실제 데이터 조회
        inventory = await get_user_inventory(user_id)
        if inventory and self.validator.validate_user_inventory(inventory):
            # 로컬 캐시에 저장
            await self.local_cache.set(user_id, inventory)
            return inventory
        
        return None
        
    except Exception as e:
        logger.error(f"인벤토리 조회 실패 ({user_id}): {e}")
        self.stats['errors'] += 1
        return None

async def invalidate_user_cache(self, user_id: str):
    """사용자 캐시 무효화"""
    try:
        await self.local_cache.invalidate(user_id)
        # 전역 캐시도 무효화
        await cache_manager.delete(f"user_data:{user_id}")
        await cache_manager.delete(f"user_inventory_display:{user_id}")
    except Exception as e:
        logger.error(f"캐시 무효화 실패 ({user_id}): {e}")

async def process_give_command(self, interaction: discord.Interaction, 
                             아이템: str, 유형: str, 
                             대상: Optional[discord.Member] = None) -> bool:
    """지급 명령어 처리"""
    try:
        self.stats['operations'] += 1
        
        # 권한 확인
        can_give, _ = await get_user_permissions(str(interaction.user.id))
        if not can_give:
            await interaction.followup.send("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
            return False
        
        # 입력 검증
        if not self.validator.validate_item_name(아이템):
            await interaction.followup.send("올바르지 않은 아이템 이름입니다.", ephemeral=True)
            return False
        
        # 유형 변환
        try:
            item_type = ItemType(유형)
        except ValueError:
            await interaction.followup.send("올바르지 않은 유형입니다.", ephemeral=True)
            return False
        
        # 배치 락 사용
        batch_key = f"give_{유형}_{time.time()}"
        async with await self._get_batch_lock(batch_key):
            return await self._execute_give_operation(
                interaction, 아이템, item_type, 대상
            )
            
    except Exception as e:
        logger.error(f"지급 명령어 처리 실패: {e}")
        self.stats['errors'] += 1
        try:
            await interaction.followup.send("명령어 처리 중 오류가 발생했습니다.", ephemeral=True)
        except:
            pass
        return False

async def _execute_give_operation(self, interaction: discord.Interaction,
                                아이템: str, item_type: ItemType,
                                대상: Optional[discord.Member]) -> bool:
    """지급 작업 실행"""
    try:
        # 타임아웃으로 보호
        return await asyncio.wait_for(
            self._do_give_operation(interaction, 아이템, item_type, 대상),
            timeout=BATCH_OPERATION_TIMEOUT
        )
    except asyncio.TimeoutError:
        logger.error("지급 작업 타임아웃")
        await interaction.followup.send("작업이 시간 초과되었습니다. 다시 시도해주세요.", ephemeral=True)
        return False

async def _do_give_operation(self, interaction: discord.Interaction,
                           아이템: str, item_type: ItemType,
                           대상: Optional[discord.Member]) -> bool:
    """실제 지급 작업"""
    # 모든 사용자 데이터 가져오기
    all_users = await get_batch_user_data()
    if not all_users:
        await interaction.followup.send("사용자 데이터를 찾을 수 없습니다.", ephemeral=True)
        return False
    
    # 대상 필터링
    filtered_users = self._filter_target_users(all_users, 대상)
    if not filtered_users:
        if 대상:
            if str(대상.id) not in all_users:
                await interaction.followup.send(f"{대상.display_name}님의 정보를 찾을 수 없습니다.", ephemeral=True)
            else:
                await interaction.followup.send("사망한 자에게는 아이템을 지급할 수 없습니다.", ephemeral=True)
        else:
            await interaction.followup.send("지급 가능한 사용자가 없습니다.", ephemeral=True)
        return False
    
    # 업데이트 데이터 생성
    updates = await self._create_give_updates(filtered_users, 아이템, item_type)
    if not updates:
        await interaction.followup.send("잘못된 지급 정보입니다.", ephemeral=True)
        return False
    
    # 데이터 업데이트
    success = await batch_update_user_inventory(updates)
    if not success:
        await interaction.followup.send("지급 처리 중 오류가 발생했습니다.", ephemeral=True)
        return False
    
    # 캐시 무효화
    for user_id in updates.keys():
        await self.invalidate_user_cache(user_id)
    
    # 결과 메시지
    target_name = (
        f"{filtered_users[str(대상.id)]['name']}님에게"
        if 대상 and str(대상.id) in filtered_users
        else "모든 러너들에게"
    )
    
    await interaction.followup.send(f"{target_name} {item_type.value} '{아이템}'을 지급했습니다.")
    logger.info(f"지급 완료: {item_type.value} '{아이템}' -> {len(updates)}명")
    return True

def _filter_target_users(self, all_users: Dict, 대상: Optional[discord.Member]) -> Dict:
    """대상 사용자 필터링"""
    filtered_users = {}
    
    try:
        if 대상:
            user_data = all_users.get(str(대상.id))
            if user_data and not is_user_dead(user_data):
                filtered_users[str(대상.id)] = user_data
        else:
            for user_id, user_data in all_users.items():
                if not is_user_dead(user_data):
                    filtered_users[user_id] = user_data
    except Exception as e:
        logger.error(f"사용자 필터링 실패: {e}")
    
    return filtered_users

async def _create_give_updates(self, filtered_users: Dict, 아이템: str, 
                             item_type: ItemType) -> Dict:
    """지급 업데이트 데이터 생성"""
    updates = {}
    
    try:
        if item_type == ItemType.COIN:
            is_valid, amount = self.validator.validate_coin_amount(아이템)
            if not is_valid:
                return {}
            
            for user_id, user_data in filtered_users.items():
                current_coins = user_data.get("coins", 0)
                new_coins = min(current_coins + amount, 999999999)  # 최대값 제한
                updates[user_id] = {"coins": new_coins}
        
        elif item_type == ItemType.ITEM:
            for user_id, user_data in filtered_users.items():
                current_items = user_data.get("items", []).copy()
                current_items.append(아이템)
                updates[user_id] = {"items": current_items}
        
        elif item_type == ItemType.OUTFIT:
            for user_id, user_data in filtered_users.items():
                current_outfits = user_data.get("outfits", []).copy()
                current_outfits.append(아이템)
                updates[user_id] = {"outfits": current_outfits}
        
        elif item_type == ItemType.PHYSICAL_STATUS:
            for user_id, user_data in filtered_users.items():
                current_status = user_data.get("physical_status", []).copy()
                current_status.append(아이템)
                updates[user_id] = {"physical_status": current_status}
        
        elif item_type == ItemType.CORRUPTION:
            is_valid, corruption_change = self.validator.validate_corruption_value(아이템)
            if not is_valid:
                return {}
            
            for user_id, user_data in filtered_users.items():
                current_corruption = user_data.get("corruption", 0)
                new_corruption = calculate_corruption_change(current_corruption, corruption_change)
                updates[user_id] = {"corruption": new_corruption}
    
    except Exception as e:
        logger.error(f"업데이트 데이터 생성 실패: {e}")
        return {}
    
    return updates

async def process_trade_command(self, interaction: discord.Interaction,
                              유형: str, 이름: str, 대상: discord.Member) -> bool:
    """거래 명령어 처리"""
    try:
        self.stats['operations'] += 1
        
        user_id = str(interaction.user.id)
        target_id = str(대상.id)
        
        # 입력 검증
        if not self.validator.validate_item_name(이름):
            await interaction.followup.send("올바르지 않은 아이템 이름입니다.", ephemeral=True)
            return False
        
        # 유형 변환 (돈 -> 코인 변환)
        try:
            if 유형 == "돈":
                item_type = ItemType.COIN
            else:
                item_type = ItemType(유형)
        except ValueError:
            await interaction.followup.send("올바르지 않은 유형입니다.", ephemeral=True)
            return False
        
        # 거래 불가 유형 확인
        if item_type in [ItemType.PHYSICAL_STATUS, ItemType.CORRUPTION]:
            await interaction.followup.send(f"{item_type.value}은 거래할 수 없습니다.", ephemeral=True)
            return False
        
        # 동시 거래 방지
        async with await self._get_operation_lock(user_id):
            return await self._execute_trade_operation(
                interaction, user_id, target_id, item_type, 이름
            )
            
    except Exception as e:
        logger.error(f"거래 명령어 처리 실패: {e}")
        self.stats['errors'] += 1
        try:
            await interaction.followup.send("거래 처리 중 오류가 발생했습니다.", ephemeral=True)
        except:
            pass
        return False

async def _execute_trade_operation(self, interaction: discord.Interaction,
                                 user_id: str, target_id: str,
                                 item_type: ItemType, 이름: str) -> bool:
    """거래 작업 실행"""
    try:
        # Admin ID 가져오기
        admin_id = await get_admin_id()
        
        # 인벤토리 확인
        giver_inventory = await self.get_cached_inventory(user_id)
        if not giver_inventory:
            await interaction.followup.send("사용자 정보를 찾을 수 없습니다.", ephemeral=True)
            return False
        
        # 수신자 확인 (Admin이 아닌 경우)
        receiver_inventory = None
        if target_id != admin_id:
            receiver_inventory = await self.get_cached_inventory(target_id)
            if not receiver_inventory:
                await interaction.followup.send("수신자 정보를 찾을 수 없습니다.", ephemeral=True)
                return False
            
            if is_user_dead(receiver_inventory):
                await interaction.followup.send("사망한 자에게는 아이템을 줄 수 없습니다.", ephemeral=True)
                return False
        
        # 거래 유효성 검사
        if not self._validate_trade(giver_inventory, item_type, 이름):
            await interaction.followup.send(f"'{이름}'을(를) 보유하고 있지 않거나 유효하지 않은 거래입니다.", ephemeral=True)
            return False
        
        # 카페 채널에서 Admin에게 코인 1 거래 감지
        if (interaction.channel_id == CAFE_CHANNEL_ID and 
            target_id == admin_id and 
            item_type == ItemType.COIN and 
            이름 == "1"):
            # 카페 시스템에 알림
            await self._notify_cafe_trade(user_id, target_id, 1)
        
        # 거래 실행
        success = await self._execute_trade(
            user_id, target_id, admin_id, item_type, 이름,
            giver_inventory, receiver_inventory
        )
        
        if not success:
            await interaction.followup.send("거래 처리 중 오류가 발생했습니다.", ephemeral=True)
            return False
        
        # 캐시 무효화
        await self.invalidate_user_cache(user_id)
        if receiver_inventory:
            await self.invalidate_user_cache(target_id)
        
        # 결과 메시지
        if target_id == admin_id:
            await interaction.followup.send(f"총괄님에게 {item_type.value} '{이름}'을 거래하였습니다.")
        else:
            await interaction.followup.send(
                f"{interaction.user.display_name}님이 {interaction.guild.get_member(int(target_id)).display_name}님에게 "
                f"{item_type.value} '{이름}'을 거래하였습니다."
            )
        
        logger.info(f"거래 완료: {user_id} -> {target_id}, {item_type.value} '{이름}'")
        return True
        
    except Exception as e:
        logger.error(f"거래 실행 실패: {e}")
        return False

def _validate_trade(self, giver_inventory: Dict, item_type: ItemType, 이름: str) -> bool:
    """거래 유효성 검사"""
    try:
        if item_type == ItemType.COIN:
            is_valid, amount = self.validator.validate_coin_amount(이름)
            if not is_valid or amount <= 0:
                return False
            return giver_inventory.get("coins", 0) >= amount
        
        elif item_type == ItemType.ITEM:
            return 이름 in giver_inventory.get("items", [])
        
        elif item_type == ItemType.OUTFIT:
            return 이름 in giver_inventory.get("outfits", [])
        
        return False
        
    except Exception as e:
        logger.error(f"거래 검증 실패: {e}")
        return False

async def _execute_trade(self, user_id: str, target_id: str, admin_id: str,
                       item_type: ItemType, 이름: str,
                       giver_inventory: Dict, receiver_inventory: Optional[Dict]) -> bool:
    """거래 실행"""
    try:
        if target_id == admin_id:
            return await self._trade_to_admin(user_id, item_type, 이름, giver_inventory)
        else:
            return await self._trade_between_users(
                user_id, target_id, item_type, 이름, giver_inventory, receiver_inventory
            )
    except Exception as e:
        logger.error(f"거래 실행 실패: {e}")
        return False

async def _trade_to_admin(self, user_id: str, item_type: ItemType, 이름: str,
                        giver_inventory: Dict) -> bool:
    """Admin에게 거래"""
    try:
        if item_type == ItemType.COIN:
            amount = int(이름)
            giver_inventory["coins"] -= amount
        elif item_type == ItemType.ITEM:
            giver_inventory["items"].remove(이름)
        elif item_type == ItemType.OUTFIT:
            giver_inventory["outfits"].remove(이름)
        
        return await update_user_inventory(
            user_id,
            giver_inventory["coins"],
            giver_inventory["items"],
            giver_inventory.get("outfits", []),
            giver_inventory.get("physical_status", []),
            giver_inventory.get("corruption", 0)
        )
    except Exception as e:
        logger.error(f"Admin 거래 실패: {e}")
        return False

async def _trade_between_users(self, user_id: str, target_id: str, item_type: ItemType,
                             이름: str, giver_inventory: Dict, receiver_inventory: Dict) -> bool:
    """사용자 간 거래"""
    try:
        if item_type == ItemType.COIN:
            amount = int(이름)
            giver_inventory["coins"] -= amount
            receiver_inventory["coins"] += amount
        elif item_type == ItemType.ITEM:
            giver_inventory["items"].remove(이름)
            receiver_inventory["items"].append(이름)
        elif item_type == ItemType.OUTFIT:
            giver_inventory["outfits"].remove(이름)
            receiver_inventory["outfits"].append(이름)
        
        # 두 사용자 인벤토리 동시 업데이트
        updates = {
            user_id: {
                "coins": giver_inventory["coins"],
                "items": giver_inventory["items"],
                "outfits": giver_inventory.get("outfits", []),
                "physical_status": giver_inventory.get("physical_status", []),
                "corruption": giver_inventory.get("corruption", 0)
            },
            target_id: {
                "coins": receiver_inventory["coins"],
                "items": receiver_inventory["items"],
                "outfits": receiver_inventory.get("outfits", []),
                "physical_status": receiver_inventory.get("physical_status", []),
                "corruption": receiver_inventory.get("corruption", 0)
            }
        }
        
        return await batch_update_user_inventory(updates)
        
    except Exception as e:
        logger.error(f"사용자 간 거래 실패: {e}")
        return False

async def _notify_cafe_trade(self, user_id: str, target_id: str, amount: int):
    """카페 시스템에 거래 알림"""
    try:
        # 동적 import로 순환 참조 방지
        from cafe import handle_trade_to_admin
        await handle_trade_to_admin(user_id, target_id, amount)
        logger.info(f"카페 거래 알림: {user_id} -> Admin")
    except Exception as e:
        logger.error(f"카페 거래 알림 실패: {e}")

async def batch_revoke_items(self, target_id: str, items: List[str],
                           item_type: Optional[str] = None) -> bool:
    """배치 아이템 회수"""
    try:
        self.stats['operations'] += 1
        
        async with await self._get_operation_lock(target_id):
            return await self._execute_revoke_operation(target_id, items, item_type)
            
    except Exception as e:
        logger.error(f"배치 회수 실패: {e}")
        self.stats['errors'] += 1
        return False

async def _execute_revoke_operation(self, target_id: str, items: List[str],
                                  item_type: Optional[str]) -> bool:
    """회수 작업 실행"""
    try:
        target_inventory = await self.get_cached_inventory(target_id)
        if not target_inventory:
            return False
        
        updated = False
        
        for item in items:
            if item_type == "신체현황":
                if item in target_inventory.get("physical_status", []):
                    target_inventory["physical_status"].remove(item)
                    updated = True
            elif item_type == "복장":
                if item in target_inventory.get("outfits", []):
                    target_inventory["outfits"].remove(item)
                    updated = True
            elif item_type == "타락도":
                is_valid, corruption_change = self.validator.validate_corruption_value(item)
                if is_valid:
                    current_corruption = target_inventory.get("corruption", 0)
                    new_corruption = calculate_corruption_change(current_corruption, -abs(corruption_change))
                    target_inventory["corruption"] = new_corruption
                    updated = True
            else:
                # 일반 아이템
                if item in target_inventory.get("items", []):
                    target_inventory["items"].remove(item)
                    updated = True
        
        if updated:
            success = await update_user_inventory(
                target_id,
                target_inventory["coins"],
                target_inventory["items"],
                target_inventory.get("outfits", []),
                target_inventory.get("physical_status", []),
                target_inventory.get("corruption", 0)
            )
            
            if success:
                await self.invalidate_user_cache(target_id)
            
            return success
        
        return False
        
    except Exception as e:
        logger.error(f"회수 실행 실패: {e}")
        return False

async def get_inventory_display(self, user_id: str) -> Optional[Dict]:
    """인벤토리 표시용 데이터 생성"""
    try:
        inventory = await self.get_cached_inventory(user_id)
        if not inventory:
            return None
        
        return {
            "coins": inventory.get("coins", 0),
            "health": inventory.get("health", "알 수 없음"),
            "items": inventory.get("items", []),
            "outfits": inventory.get("outfits", []),
            "physical_status": inventory.get("physical_status", []),
            "corruption": inventory.get("corruption", 0)
        }
        
    except Exception as e:
        logger.error(f"인벤토리 표시 데이터 생성 실패: {e}")
        return None

def get_stats(self) -> Dict:
    """성능 통계 반환"""
    total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
    hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0
    
    return {
        'operations': self.stats['operations'],
        'cache_hit_rate': hit_rate,
        'total_errors': self.stats['errors'],
        'cache_size': len(self.local_cache.cache),
        'active_locks': len(self.operation_locks)
    }

async def shutdown(self):
    """매니저 종료"""
    try:
        logger.info("인벤토리 매니저 종료 시작")
        
        # 백그라운드 작업 취소
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 캐시 정리
        await self.local_cache.invalidate_all()
        
        # 통계 출력
        stats = self.get_stats()
        logger.info(f"인벤토리 매니저 종료 - 통계: {stats}")
        
    except Exception as e:
        logger.error(f"인벤토리 매니저 종료 실패: {e}")
```

# === 자동완성 함수들 ===

async def create_item_autocomplete_choices(user_id: str, 유형: str, current: str) -> List[app_commands.Choice]:
“”“아이템 자동완성 선택지 생성”””
try:
manager = get_inventory_manager()

```
    if 유형 in ["돈", "코인"]:
        user_data = await manager.get_cached_inventory(user_id)
        if user_data:
            current_balance = user_data.get("coins", 0)
            return [
                app_commands.Choice(
                    name=f"현재잔액: {current_balance}, 정수로 입력하세요",
                    value="0"
                )
            ]
    
    # 사용자 인벤토리에서 아이템 목록 가져오기
    user_data = await manager.get_cached_inventory(user_id)
    if not user_data:
        return []
    
    items = []
    if 유형 == "아이템":
        items = user_data.get("items", [])
    elif 유형 == "복장":
        items = user_data.get("outfits", [])
    else:
        return []
    
    # 현재 입력에 따라 필터링
    if current:
        filtered_items = [
            item for item in items
            if current.lower() in item.lower()
        ]
    else:
        filtered_items = items
    
    # 중복 제거 및 정렬
    unique_items = sorted(list(set(filtered_items)))
    
    return [
        app_commands.Choice(name=item[:100], value=item[:100])  # Discord 제한
        for item in unique_items[:MAX_AUTOCOMPLETE_ITEMS]
    ]
    
except Exception as e:
    logger.error(f"자동완성 생성 실패: {e}")
    return []
```

async def create_revoke_autocomplete_choices(target_id: str, current: str) -> List[app_commands.Choice]:
“”“회수 자동완성 선택지 생성”””
try:
manager = get_inventory_manager()
target_inventory = await manager.get_cached_inventory(target_id)
if not target_inventory:
return []

```
    # 모든 회수 가능한 아이템 수집
    all_items = []
    all_items.extend(target_inventory.get("items", []))
    all_items.extend(target_inventory.get("outfits", []))
    all_items.extend(target_inventory.get("physical_status", []))
    
    # 타락도 옵션 추가
    current_corruption = target_inventory.get("corruption", 0)
    if current_corruption > 0:
        all_items.append(f"타락도:{current_corruption}")
    
    # 현재 입력에 따라 필터링
    if current:
        filtered_items = [
            item for item in all_items
            if current.lower() in item.lower()
        ]
    else:
        filtered_items = all_items
    
    # 중복 제거 및 정렬
    unique_items = sorted(list(set(filtered_items)))
    
    return [
        app_commands.Choice(name=item[:100], value=item[:100])
        for item in unique_items[:MAX_AUTOCOMPLETE_ITEMS]
    ]
    
except Exception as e:
    logger.error(f"회수 자동완성 생성 실패: {e}")
    return []
```

# === 전역 인스턴스 ===

inventory_manager: Optional[InventoryManager] = None

def get_inventory_manager() -> InventoryManager:
“”“인벤토리 매니저 인스턴스 반환”””
global inventory_manager
if inventory_manager is None:
inventory_manager = InventoryManager()
return inventory_manager

async def shutdown_inventory_system():
“”“인벤토리 시스템 종료”””
global inventory_manager
if inventory_manager:
await inventory_manager.shutdown()
inventory_manager = None

# === 유틸리티 함수들 ===

async def validate_user_permissions(user_id: str, operation: OperationType) -> Tuple[bool, str]:
“”“사용자 권한 검증”””
try:
can_give, can_revoke = await get_user_permissions(user_id)

```
    if operation == OperationType.GIVE and not can_give:
        return False, "지급 권한이 없습니다."
    elif operation == OperationType.REVOKE and not can_revoke:
        return False, "회수 권한이 없습니다."
    elif operation == OperationType.TRADE:
        # 거래는 모든 사용자 가능
        pass
    
    return True, ""
    
except Exception as e:
    logger.error(f"권한 검증 실패: {e}")
    return False, "권한 확인 중 오류가 발생했습니다."
```

async def get_system_health() -> Dict:
“”“시스템 상태 확인”””
try:
manager = get_inventory_manager()
return {
“status”: “healthy”,
“stats”: manager.get_stats(),
“timestamp”: datetime.now().isoformat()
}
except Exception as e:
logger.error(f”시스템 상태 확인 실패: {e}”)
return {
“status”: “error”,
“error”: str(e),
“timestamp”: datetime.now().isoformat()
}