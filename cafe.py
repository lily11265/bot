
# cafe.py
import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import discord
import json
import os

from utility import (
    get_user_inventory, update_user_inventory, get_batch_user_data,
    cache_manager
)

logger = logging.getLogger(__name__)

# 상수 정의
CAFE_CHANNEL_ID = 1388391607983800382
DICE_BOT_ID = 218010938807287808
ADMIN_ID = "1007172975222603798"
AWAKENING_DURATION = 86400  # 24시간 (초 단위)

# 멤버 이름 목록 (하드코딩)
MEMBER_NAMES = {
    "아카시 하지메",
    "펀처",
    "유진석",
    "휘슬",
    "배달기사",
    "페이",
    "로메즈 아가레스",
    "레이나 하트베인",
    "비비",
    "오카미 나오하",
    "카라트에크",
    "토트",
    "처용",
    "멀 플리시",
    "코발트윈드",
    "옥타",
    "베레니케",
    "안드라 블랙",
    "봉고 3호",
    "몰",
    "베니",
    "백야",
    "루치페르",
    "벨사이르 드라켄리트",
    "불스",
    "퓨어 메탈",
    "노 단투",
    "라록",
    "아카이브",
    "베터",
    "메르쿠리",
    "마크-112",
    "스푸트니크 2세",
    "이터니티",
    "커피머신"
}

class CafeDiceSystem:
    """카페 주사위 시스템"""
    
    def __init__(self, bot):
        self.bot = bot
        self.awakening_file = "awakening_data.json"
        self.daily_dice_file = "daily_dice_data.json"
        self.awakening_tasks = {}  # user_id: task
        self.daily_dice_users = set()  # 오늘 주사위 굴린 유저들
        self.recent_trades = {}  # user_id: timestamp - 최근 거래 기록
        
        logger.info("카페 주사위 시스템 초기화 시작")
        
        # 저장된 데이터 로드
        self._load_awakening_data()
        self._load_daily_dice_data()
        
        # 정리 작업 시작
        self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
        
        logger.info("카페 주사위 시스템 초기화 완료")
    
    async def record_trade_to_admin(self, user_id: str):
        """Admin에게 거래 기록"""
        self.recent_trades[user_id] = datetime.now()
        logger.info(f"거래 기록: {user_id} -> Admin")
        
        # 10분 후 자동 삭제
        await asyncio.sleep(600)
        if user_id in self.recent_trades:
            del self.recent_trades[user_id]
    
    def _check_recent_trade(self, user_id: str) -> bool:
        """최근 거래 확인 (5분 이내)"""
        if user_id not in self.recent_trades:
            return False
            
        trade_time = self.recent_trades[user_id]
        elapsed = (datetime.now() - trade_time).total_seconds()
        
        # 5분 이내 거래만 유효
        return elapsed <= 300
    
    def _parse_name_and_health(self, display_name: str) -> Tuple[Optional[str], Optional[int]]:
        """디스플레이 이름에서 멤버 이름과 체력 추출"""
        logger.debug(f"이름과 체력 파싱 시도: {display_name}")
        
        # 하드코딩된 멤버 이름 중 일치하는 것 찾기
        for member_name in MEMBER_NAMES:
            if member_name in display_name:
                logger.debug(f"멤버 이름 찾음: {member_name}")
                
                # 이름 뒤의 숫자 찾기
                # 이름 이후의 부분 추출
                name_end = display_name.find(member_name) + len(member_name)
                remaining = display_name[name_end:]
                
                # 숫자 찾기 (/, 공백, 또는 다른 구분자 뒤)
                numbers = re.findall(r'\d+', remaining)
                if numbers:
                    health = int(numbers[0])  # 첫 번째 숫자를 체력으로
                    logger.debug(f"체력 찾음: {health}")
                    return member_name, health
                else:
                    # 숫자가 없으면 전체에서 마지막 숫자 찾기
                    all_numbers = re.findall(r'\d+', display_name)
                    if all_numbers:
                        health = int(all_numbers[-1])
                        logger.debug(f"체력 찾음 (전체에서): {health}")
                        return member_name, health
                    else:
                        logger.debug(f"체력을 찾을 수 없음")
                        return member_name, None
        
        logger.debug(f"하드코딩된 멤버 이름과 일치하지 않음: {display_name}")
        return None, None
    
    def _find_member_by_hardcoded_name(self, guild: discord.Guild, member_name: str) -> Optional[discord.Member]:
        """하드코딩된 이름으로 멤버 찾기"""
        logger.debug(f"하드코딩된 이름으로 멤버 찾기: {member_name}")
        logger.debug(f"길드 멤버 수: {len(guild.members)}")
        
        # 디버깅: 모든 멤버 출력
        logger.debug("=== 서버 멤버 목록 ===")
        for idx, member in enumerate(guild.members):
            logger.debug(f"{idx}. {member.display_name} (실제이름: {member.name}, ID: {member.id})")
        logger.debug("===================")
        
        # 정확한 일치 먼저 시도
        for member in guild.members:
            # 디스플레이 이름에 해당 멤버 이름이 포함되어 있는지 확인
            if member_name in member.display_name:
                logger.debug(f"멤버 찾음 (디스플레이): {member.display_name} (ID: {member.id})")
                return member
            
            # 실제 사용자 이름도 확인
            if member.name == member_name:
                logger.debug(f"멤버 찾음 (실제 이름): {member.name} (ID: {member.id})")
                return member
            
            # 대소문자 구분 없이 비교
            if member_name.lower() in member.display_name.lower():
                logger.debug(f"멤버 찾음 (대소문자 무시): {member.display_name} (ID: {member.id})")
                return member
            
            if member_name.lower() == member.name.lower():
                logger.debug(f"멤버 찾음 (실제 이름, 대소문자 무시): {member.name} (ID: {member.id})")
                return member
        
        # 부분 일치 시도 (공백, 특수문자 제거)
        clean_member_name = re.sub(r'[^\w가-힣]', '', member_name)
        for member in guild.members:
            clean_display = re.sub(r'[^\w가-힣]', '', member.display_name)
            clean_username = re.sub(r'[^\w가-힣]', '', member.name)
            
            if clean_member_name in clean_display or clean_member_name == clean_username:
                logger.debug(f"멤버 찾음 (정리된 이름): {member.display_name} (ID: {member.id})")
                return member
        
        logger.error(f"멤버를 찾을 수 없음: {member_name}")
        logger.error(f"서버에 {len(guild.members)}명의 멤버가 있지만 '{member_name}'와 일치하는 멤버가 없습니다")
        return None
    
    async def handle_dice_message(self, message: discord.Message):
        """주사위 메시지 처리"""
        logger.debug(f"메시지 처리 시작 - 채널: {message.channel.id}, 작성자: {message.author.id}")
        
        # 카페 채널 확인
        if message.channel.id != CAFE_CHANNEL_ID:
            logger.debug(f"카페 채널이 아님: {message.channel.id} != {CAFE_CHANNEL_ID}")
            return False
            
        # 봇 확인
        if message.author.id != DICE_BOT_ID:
            logger.debug(f"주사위 봇이 아님: {message.author.id} != {DICE_BOT_ID}")
            return False
        
        logger.info(f"주사위 봇 메시지 감지: {message.content}")
        
        # 길드 정보 확인
        logger.debug(f"길드: {message.guild.name} (ID: {message.guild.id})")
        logger.debug(f"길드 멤버 수: {len(message.guild.members)}")
        
        # 봇의 권한 확인
        bot_member = message.guild.me
        logger.debug(f"봇의 권한: {bot_member.guild_permissions.value}")
        logger.debug(f"멤버 보기 권한: {bot_member.guild_permissions.view_channel}")
        
        # 메시지 형식 확인 및 파싱
        dice_result = self._parse_dice_message(message.content)
        if not dice_result:
            logger.warning(f"메시지 파싱 실패: {message.content}")
            return False
        
        display_name, dice_value = dice_result
        logger.info(f"파싱 성공 - 이름: {display_name}, 주사위값: {dice_value}")
        
        # 하드코딩된 이름으로 멤버 찾기
        member_name, parsed_health = self._parse_name_and_health(display_name)
        
        if not member_name:
            logger.error(f"하드코딩된 멤버 이름과 일치하지 않음: {display_name}")
            return False
        
        logger.info(f"하드코딩된 이름 찾음: {member_name}, 체력: {parsed_health}")
        
        member = self._find_member_by_hardcoded_name(message.guild, member_name)
        
        if not member:
            logger.error(f"멤버를 찾을 수 없음: {member_name}")
            
            # 추가 디버깅: 유사한 이름 찾기
            similar_members = []
            for m in message.guild.members:
                if any(part in m.display_name.lower() for part in member_name.lower().split()):
                    similar_members.append(f"{m.display_name} (ID: {m.id})")
            
            if similar_members:
                logger.info(f"유사한 이름의 멤버들: {', '.join(similar_members[:5])}")
            
            return False
        
        logger.info(f"멤버 찾음: {member.display_name} (ID: {member.id})")
        
        # 거래 확인
        user_id = str(member.id)
        if not self._check_recent_trade(user_id):
            logger.warning(f"{member.display_name}님은 최근 거래 기록이 없음")
            # 거래 없이도 처리할지 선택 (현재는 경고만 출력)
            return False  # 거래 필수로 하려면 주석 해제
        
        logger.info(f"{member.display_name}님이 주사위 {dice_value} 굴림 - 처리 시작")
        
        # 주사위 결과에 따른 처리
        try:
            if dice_value >= 90:
                logger.info("90 이상 - 각성 효과 처리")
                await self._handle_awakening(member)
            elif 4 <= dice_value <= 10:
                logger.info("4-10 - 개인 데미지 처리 (-30)")
                await self._handle_damage(member, -30)
            elif 1 <= dice_value <= 3:
                logger.info("1-3 - 범위 데미지 처리")
                await self._handle_area_damage(message.channel, member)
            else:
                logger.info(f"처리 없음 - 주사위값: {dice_value}")
            
            # 일일 주사위 기록
            self.daily_dice_users.add(user_id)
            self._save_daily_dice_data()
            
            # 거래 기록 제거
            if user_id in self.recent_trades:
                del self.recent_trades[user_id]
            
            logger.info(f"주사위 처리 완료")
            return True
            
        except Exception as e:
            logger.error(f"주사위 처리 실패: {e}", exc_info=True)
            return False
    
    def _parse_dice_message(self, content: str) -> Optional[tuple]:
        """주사위 메시지 파싱"""
        logger.debug(f"메시지 파싱 시도: {content}")
        
        # 패턴: `이름`님이 :game_die:주사위를 굴려 ****숫자**** 나왔습니다.
        pattern = r"`(.+?)`님이.*?주사위를 굴려.*?(\d+).*?나왔습니다"
        match = re.search(pattern, content)
        
        if match:
            display_name = match.group(1)
            dice_value = int(match.group(2))
            logger.debug(f"파싱 성공: {display_name}, {dice_value}")
            return (display_name, dice_value)
        
        logger.debug("파싱 실패")
        return None
    
    async def handle_trade_command(self, user_id: str, target_id: str, amount: int):
        """거래 명령어 처리 (Admin 거래 감지용)"""
        if target_id == ADMIN_ID and amount == 1:
            logger.info(f"Admin 거래 감지: {user_id} -> {amount}코인")
            asyncio.create_task(self.record_trade_to_admin(user_id))
    
    def _load_awakening_data(self):
        """각성 데이터 로드"""
        if os.path.exists(self.awakening_file):
            try:
                with open(self.awakening_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 각성 타이머 복원
                restored_count = 0
                for user_id, info in data.items():
                    end_time = datetime.fromisoformat(info['end_time'])
                    if end_time > datetime.now():
                        # 아직 유효한 각성 상태면 타이머 재시작
                        remaining = (end_time - datetime.now()).total_seconds()
                        self._start_awakening_timer(user_id, remaining)
                        restored_count += 1
                
                logger.info(f"각성 데이터 로드 완료: {restored_count}명 복원")
                        
            except Exception as e:
                logger.error(f"각성 데이터 로드 실패: {e}")
    
    def _load_daily_dice_data(self):
        """일일 주사위 데이터 로드"""
        if os.path.exists(self.daily_dice_file):
            try:
                with open(self.daily_dice_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 오늘 날짜 확인
                today = datetime.now().strftime('%Y-%m-%d')
                if data.get('date') == today:
                    self.daily_dice_users = set(data.get('users', []))
                    logger.info(f"오늘 주사위 굴린 유저: {len(self.daily_dice_users)}명")
                else:
                    # 날짜가 다르면 초기화
                    logger.info("날짜가 변경되어 일일 주사위 데이터 초기화")
                    self.daily_dice_users = set()
                    self._save_daily_dice_data()
                    
            except Exception as e:
                logger.error(f"일일 주사위 데이터 로드 실패: {e}")
    
    def _save_awakening_data(self):
        """각성 데이터 저장"""
        try:
            data = {}
            current_time = datetime.now()
            
            # 진행 중인 각성 상태만 저장
            for user_id, task in self.awakening_tasks.items():
                if not task.done():
                    # 간단히 24시간 후로 계산
                    data[user_id] = {
                        'end_time': (current_time + timedelta(seconds=AWAKENING_DURATION)).isoformat(),
                        'started_at': current_time.isoformat()
                    }
            
            with open(self.awakening_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"각성 데이터 저장: {len(data)}명")
                
        except Exception as e:
            logger.error(f"각성 데이터 저장 실패: {e}")
    
    def _save_daily_dice_data(self):
        """일일 주사위 데이터 저장"""
        try:
            data = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'users': list(self.daily_dice_users)
            }
            
            with open(self.daily_dice_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f"일일 주사위 데이터 저장: {len(self.daily_dice_users)}명")
                
        except Exception as e:
            logger.error(f"일일 주사위 데이터 저장 실패: {e}")
    
    async def _periodic_cleanup(self):
        """주기적 정리 작업"""
        while True:
            try:
                await asyncio.sleep(3600)  # 1시간마다
                
                # 자정에 일일 주사위 데이터 초기화
                now = datetime.now()
                if now.hour == 0 and now.minute < 1:
                    self.daily_dice_users.clear()
                    self._save_daily_dice_data()
                    logger.info("일일 주사위 데이터 초기화됨")
                
                # 완료된 각성 타이머 정리
                completed_tasks = [uid for uid, task in self.awakening_tasks.items() if task.done()]
                for uid in completed_tasks:
                    del self.awakening_tasks[uid]
                
                if completed_tasks:
                    self._save_awakening_data()
                    logger.info(f"완료된 각성 타이머 {len(completed_tasks)}개 정리")
                
                # 오래된 거래 기록 정리
                current_time = datetime.now()
                expired_trades = [
                    uid for uid, trade_time in self.recent_trades.items()
                    if (current_time - trade_time).total_seconds() > 600
                ]
                for uid in expired_trades:
                    del self.recent_trades[uid]
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"주기적 정리 실패: {e}")
    
    async def _handle_awakening(self, member: discord.Member):
        """각성 효과 처리"""
        user_id = str(member.id)
        logger.info(f"각성 처리 시작 - {member.display_name} (ID: {user_id})")
        
        # 이미 각성 상태인지 확인
        if user_id in self.awakening_tasks and not self.awakening_tasks[user_id].done():
            logger.info(f"{member.display_name}님은 이미 각성 상태")
            return
        
        # 오늘 이미 주사위를 굴렸는지 확인
        if user_id in self.daily_dice_users:
            logger.info(f"{member.display_name}님은 오늘 이미 주사위를 굴림")
            return
        
        # 닉네임에 [각성] 추가
        current_nick = member.display_name
        logger.debug(f"현재 닉네임: {current_nick}")
        
        if not current_nick.startswith("[각성]"):
            new_nick = f"[각성]{current_nick}"
            logger.debug(f"새 닉네임: {new_nick}")
            
            try:
                await member.edit(nick=new_nick[:32])  # Discord 닉네임 길이 제한
                logger.info(f"{member.display_name}님에게 각성 효과 부여 성공")
                
                # 24시간 타이머 시작
                self._start_awakening_timer(user_id, AWAKENING_DURATION)
                
                # 종료 시간 캐시에 저장
                end_time = datetime.now() + timedelta(seconds=AWAKENING_DURATION)
                await cache_manager.set(f"awakening_end:{user_id}", end_time.isoformat(), ex=AWAKENING_DURATION)
                logger.debug(f"각성 종료 시간: {end_time.isoformat()}")
                
                self._save_awakening_data()
                
            except discord.Forbidden:
                logger.error(f"닉네임 변경 권한 없음: {member.display_name}")
            except Exception as e:
                logger.error(f"각성 효과 부여 실패: {e}", exc_info=True)
        else:
            logger.info(f"{member.display_name}님은 이미 [각성] 효과 보유")
    
    def _start_awakening_timer(self, user_id: str, duration: float):
        """각성 타이머 시작"""
        logger.debug(f"각성 타이머 시작 - {user_id}, {duration}초")
        
        if user_id in self.awakening_tasks:
            self.awakening_tasks[user_id].cancel()
            logger.debug(f"기존 타이머 취소됨")
        
        self.awakening_tasks[user_id] = asyncio.create_task(
            self._remove_awakening_after(user_id, duration)
        )
    
    async def _remove_awakening_after(self, user_id: str, duration: float):
        """일정 시간 후 각성 효과 제거"""
        try:
            logger.debug(f"각성 제거 대기 시작 - {user_id}, {duration}초")
            await asyncio.sleep(duration)
            
            logger.info(f"각성 제거 시작 - {user_id}")
            
            # 멤버 찾기
            member = None
            for guild in self.bot.guilds:
                member = guild.get_member(int(user_id))
                if member:
                    logger.debug(f"멤버 찾음: {member.display_name}")
                    break
            
            if member and member.display_name.startswith("[각성]"):
                new_nick = member.display_name[4:]  # "[각성]" 제거
                try:
                    await member.edit(nick=new_nick)
                    logger.info(f"{user_id}의 각성 효과 제거 성공")
                except Exception as e:
                    logger.error(f"각성 제거 실패: {e}")
            else:
                logger.warning(f"멤버를 찾을 수 없거나 [각성] 효과가 없음")
            
            # 캐시 정리
            await cache_manager.delete(f"awakening_end:{user_id}")
            
            # 타스크 정리
            if user_id in self.awakening_tasks:
                del self.awakening_tasks[user_id]
            
            self._save_awakening_data()
            
        except asyncio.CancelledError:
            logger.debug(f"각성 타이머 취소됨 - {user_id}")
        except Exception as e:
            logger.error(f"각성 제거 실패: {e}", exc_info=True)
    
    def _extract_health_from_name(self, display_name: str) -> Optional[int]:
        """닉네임에서 체력 추출"""
        logger.debug(f"체력 추출 시도: {display_name}")
        
        # 하드코딩된 멤버 이름으로 파싱
        member_name, health = self._parse_name_and_health(display_name)
        
        if health is not None:
            logger.debug(f"체력 찾음: {health}")
            return health
        
        # 폴백: 닉네임의 마지막 숫자 찾기
        numbers = re.findall(r'\d+', display_name)
        if numbers:
            health = int(numbers[-1])
            logger.debug(f"체력 찾음 (폴백): {health}")
            return health
        
        logger.debug("체력을 찾을 수 없음")
        return None
    
    async def _handle_damage(self, member: discord.Member, damage: int):
        """데미지 처리"""
        user_id = str(member.id)
        logger.info(f"데미지 처리 시작 - {member.display_name}, 데미지: {damage}")
        
        # 현재 체력 확인
        current_health = self._extract_health_from_name(member.display_name)
        logger.debug(f"현재 체력: {current_health}")
        
        if current_health is None:
            logger.warning(f"{member.display_name}의 체력을 찾을 수 없음")
            return
        
        # 새 체력 계산
        new_health = max(0, current_health + damage)  # damage가 음수이므로 +
        logger.info(f"새 체력: {current_health} -> {new_health}")
        
        # 닉네임과 스프레드시트 동시 업데이트
        await self._update_member_health(member, new_health)
    
    async def _handle_area_damage(self, channel: discord.TextChannel, dice_roller: discord.Member):
        """범위 데미지 처리"""
        logger.info(f"범위 데미지 처리 시작 - 주사위 굴린 사람: {dice_roller.display_name}")
        
        # 지난 5분간의 메시지 수집
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        affected_members = set()
        channel_taggers = set()
        
        message_count = 0
        async for msg in channel.history(after=five_minutes_ago, limit=100):
            message_count += 1
            if msg.author.bot:
                continue
                
            # 채널 태그 확인 (# 으로 시작하는 멘션)
            if re.search(r'<#\d+>', msg.content):
                channel_taggers.add(msg.author.id)
                logger.debug(f"채널 태그한 사람: {msg.author.display_name}")
            
            affected_members.add(msg.author)
        
        logger.debug(f"5분간 메시지 수: {message_count}, 참여자 수: {len(affected_members)}")
        
        # 채널 태그한 사람 제외
        targets = [m for m in affected_members if m.id not in channel_taggers and m.id != dice_roller.id]
        
        logger.info(f"범위 데미지 대상: {len(targets)}명")
        for target in targets:
            logger.debug(f"대상: {target.display_name}")
        
        # 각 대상에게 데미지
        for member in targets:
            await self._handle_damage(member, -20)
            await asyncio.sleep(0.5)  # Rate limit 방지
    
    async def _update_member_health(self, member: discord.Member, new_health: int):
        """멤버 체력 업데이트 (닉네임 + 스프레드시트)"""
        current_nick = member.display_name
        user_id = str(member.id)
        logger.debug(f"닉네임 업데이트 시작 - 현재: {current_nick}, 새 체력: {new_health}")
        
        # 기존 체력 숫자 제거
        health_removed = re.sub(r'\d+(?!.*\d)', '', current_nick).strip()
        logger.debug(f"숫자 제거 후: {health_removed}")
        
        # [사망] 효과 처리
        if new_health <= 0:
            if not health_removed.startswith("[사망]"):
                health_removed = f"[사망]{health_removed}"
                logger.info(f"[사망] 효과 추가")
        else:
            # 기존 [사망] 제거
            if health_removed.startswith("[사망]"):
                health_removed = health_removed[4:]
                logger.info(f"[사망] 효과 제거")
        
        # 새 닉네임 생성
        new_nick = f"{health_removed} {new_health}"
        logger.debug(f"새 닉네임: {new_nick}")
        
        # 닉네임 업데이트
        try:
            await member.edit(nick=new_nick[:32])
            logger.info(f"{member.name}의 닉네임 체력 업데이트 성공: {new_health}")
        except discord.Forbidden:
            logger.error(f"닉네임 변경 권한 없음: {member.display_name}")
        except Exception as e:
            logger.error(f"닉네임 업데이트 실패: {e}", exc_info=True)
        
        # 스프레드시트 업데이트
        try:
            logger.info(f"스프레드시트 체력 업데이트 시작 - {user_id}, 체력: {new_health}")
            
            # 현재 사용자 데이터 가져오기
            user_data = await get_user_inventory(user_id)
            if not user_data:
                logger.warning(f"유저 데이터를 찾을 수 없음: {user_id}")
                return
            
            # health 필드를 포함하여 업데이트
            success = await update_user_inventory(
                user_id,
                coins=user_data.get("coins"),
                items=user_data.get("items"),
                outfits=user_data.get("outfits"),
                physical_status=user_data.get("physical_status"),
                corruption=user_data.get("corruption"),
                health=str(new_health)  # health 업데이트
            )
            
            if success:
                logger.info(f"스프레드시트 체력 업데이트 성공 - {user_id}: {new_health}")
            else:
                logger.error(f"스프레드시트 체력 업데이트 실패 - {user_id}")
                
        except Exception as e:
            logger.error(f"스프레드시트 업데이트 중 오류: {e}", exc_info=True)
    
    async def shutdown(self):
        """시스템 종료"""
        logger.info("카페 시스템 종료 시작")
        
        # 진행 중인 타이머 취소
        for user_id, task in self.awakening_tasks.items():
            if not task.done():
                task.cancel()
                logger.debug(f"각성 타이머 취소: {user_id}")
        
        # 정리 작업 취소
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
        
        # 데이터 저장
        self._save_awakening_data()
        self._save_daily_dice_data()
        
        logger.info("카페 시스템 종료 완료")

# 전역 인스턴스
cafe_dice_system = None

def init_cafe_system(bot):
    """카페 시스템 초기화"""
    global cafe_dice_system
    logger.info("카페 시스템 초기화 함수 호출")
    cafe_dice_system = CafeDiceSystem(bot)
    return cafe_dice_system

def get_cafe_system():
    """카페 시스템 인스턴스 반환"""
    return cafe_dice_system

async def handle_message(message: discord.Message):
    """메시지 처리"""
    logger.debug(f"카페 메시지 핸들러 호출 - 채널: {message.channel.id}, 작성자: {message.author.id}, 봇: {message.author.bot}")
    
    if message.author.bot and message.author.id == DICE_BOT_ID:
        logger.info(f"주사위 봇 메시지 감지됨")
        system = get_cafe_system()
        if system:
            return await system.handle_dice_message(message)
        else:
            logger.error("카페 시스템이 초기화되지 않음")
    return False

async def handle_trade_to_admin(user_id: str, target_id: str, amount: int):
    """Admin 거래 처리"""
    system = get_cafe_system()
    if system:
        await system.handle_trade_command(user_id, target_id, amount)