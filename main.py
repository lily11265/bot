
# main.py - 최적화된 버전
import asyncio
import logging
import pytz
import traceback
from concurrent.futures import ThreadPoolExecutor
import discord
from discord import app_commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import signal
import sys

# 모듈 import (최적화됨)
from utility import (
    cache_manager, get_user_inventory, get_user_permissions, 
    increment_daily_values, cache_daily_metadata
)
from BambooForest import init_bamboo_system, handle_message, handle_reaction
from shop import (
    get_inventory_manager, create_item_autocomplete_choices, 
    create_revoke_autocomplete_choices
)

from cafe import init_cafe_system, handle_message as handle_cafe_message


# 로깅 설정 (최적화)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8', mode='a'),  # append 모드
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 봇 설정
BOT_TOKEN = "MTMxMzg3NzE1ODI3NTU4NDA4MA.G-4kyD.WnPN1RaabtWnfVwea6XErLH4C1zQpxAqNm0De4"

# Discord 설정 최적화 (24시간 운영에 맞춤)
intents = discord.Intents.default()
intents.members = True  # 멤버 인텐트 필수 활성화!
intents.message_content = True
intents.dm_messages = True
intents.guilds = True
intents.guild_messages = True
intents.presences = False  # Presence intent 비활성화 (성능 향상)
intents.typing = False

# 봇 인스턴스 생성 (최적화된 설정)
bot = discord.Client(
    intents=intents,
    heartbeat_timeout=60,
    guild_ready_timeout=10.0,
    assume_unsync_clock=False,
    max_messages=200,  # 메시지 캐시 크기 감소
    connector=None,  # 자동 커넥터 사용
    proxy=None,
    proxy_auth=None,
    shard_id=None,
    shard_count=None,
    application_id=None,
    member_cache_flags=discord.MemberCacheFlags.all(),  # 모든 멤버 캐시로 변경!
    chunk_guilds_at_startup=True,  # 시작 시 길드 청킹 활성화로 변경!
    status=discord.Status.online,
    activity=None,
    allowed_mentions=discord.AllowedMentions.none(),  # 멘션 비활성화로 성능 향상
    enable_debug_events=False
)

tree = app_commands.CommandTree(bot)

# 전역 스레드 풀 (크기 최적화)
thread_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='BotWorker')

class BotManager:
    """봇 관리 클래스 (최적화)"""
    
    def __init__(self):
        self.scheduler = None
        self.bamboo_system = None
        self.inventory_manager = None
        self.gateway_task = None
        self.health_check_interval = 300  # 5분마다 헬스체크
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self._shutdown_event = asyncio.Event()
        self.cafe_system = None

    async def initialize(self):
        """봇 초기화 (백그라운드 작업 최적화)"""
        try:
            # 대나무숲 시스템 초기화
            self.bamboo_system = init_bamboo_system(bot)
            self.cafe_system = init_cafe_system(bot)

            # 인벤토리 매니저 초기화
            self.inventory_manager = get_inventory_manager()
            
            # 캐시 관리자 시작
            await cache_manager.start_background_cleanup()
            
            # 메타데이터 캐싱
            await cache_daily_metadata()
            
            # 스케줄러 설정
            self._setup_scheduler()
            
            # Gateway 모니터링 시작
            self.gateway_task = asyncio.create_task(self._monitor_gateway())
            
            logger.info("봇 초기화 완료")
            
        except Exception as e:
            logger.error(f"봇 초기화 실패: {e}")
            raise

    def _setup_scheduler(self):
        """스케줄러 설정 (메모리 효율성 향상)"""
        self.scheduler = AsyncIOScheduler(
            timezone=pytz.timezone("Asia/Seoul"),
            job_defaults={
                'misfire_grace_time': 60,
                'coalesce': True,  # 중복 작업 병합
                'max_instances': 1  # 동시 실행 방지
            }
        )
        
        # 일일 메타데이터 캐싱 (새벽 5시)
        self.scheduler.add_job(
            self._safe_cache_daily_metadata, 
            'cron', 
            hour=5, 
            minute=0,
            id='daily_cache',
            replace_existing=True
        )
        
        # 일일 코인 증가 (자정)
        self.scheduler.add_job(
            self._safe_increment_daily_values, 
            'cron', 
            hour=0, 
            minute=0,
            id='daily_coins',
            replace_existing=True
        )
        
        self.scheduler.start()
        logger.info("스케줄러 시작됨")

    async def _safe_cache_daily_metadata(self):
        """안전한 메타데이터 캐싱"""
        try:
            await cache_daily_metadata()
        except Exception as e:
            logger.error(f"일일 메타데이터 캐싱 실패: {e}")

    async def _safe_increment_daily_values(self):
        """안전한 일일 코인 증가"""
        try:
            await increment_daily_values()
        except Exception as e:
            logger.error(f"일일 코인 증가 실패: {e}")

    async def _monitor_gateway(self):
        """Gateway 상태 모니터링 (최적화)"""
        consecutive_high_latency = 0
        
        while not self._shutdown_event.is_set():
            try:
                if bot.is_closed():
                    logger.warning("봇 연결이 끊어졌습니다. 재연결 시도 중...")
                    self.reconnect_attempts += 1
                    
                    if self.reconnect_attempts > self.max_reconnect_attempts:
                        logger.error("최대 재연결 시도 횟수 초과")
                        break
                    
                    await asyncio.sleep(30)  # 재연결 전 대기
                    continue
                
                latency = bot.latency * 1000  # ms 단위로 변환
                
                if latency < 0:  # 연결되지 않은 상태
                    logger.warning("봇이 연결되지 않은 상태입니다")
                elif latency > 2000:  # 2초 이상 지연
                    consecutive_high_latency += 1
                    logger.warning(f"높은 지연 시간 감지: {latency:.2f}ms (연속 {consecutive_high_latency}회)")
                    
                    if consecutive_high_latency >= 3:
                        logger.error("지속적인 높은 지연 시간 - 재연결 고려 필요")
                else:
                    consecutive_high_latency = 0
                    if latency > 1000:  # 1초 이상 지연
                        logger.info(f"지연 시간: {latency:.2f}ms")
                
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Gateway 모니터링 실패: {e}")
                await asyncio.sleep(30)

    async def _shutdown_cafe_system(self):
        """카페 시스템 안전 종료"""
        try:
            await self.cafe_system.shutdown()
        except Exception as e:
            logger.error(f"카페 시스템 종료 실패: {e}")

    async def shutdown(self):
        """봇 종료 처리 (리소스 정리 최적화)"""
        logger.info("봇 종료 시작...")
        self._shutdown_event.set()
        
        # 종료 작업들을 병렬로 처리
        shutdown_tasks = []
        
        # 스케줄러 종료
        if self.scheduler and self.scheduler.running:
            shutdown_tasks.append(
                asyncio.create_task(self._shutdown_scheduler())
            )
        
        # Gateway 모니터링 종료
        if self.gateway_task and not self.gateway_task.done():
            self.gateway_task.cancel()
            shutdown_tasks.append(self.gateway_task)
        
        # 대나무숲 시스템 종료
        if self.bamboo_system:
            shutdown_tasks.append(
                asyncio.create_task(self._shutdown_bamboo_system())
            )
        
        if self.cafe_system:
            shutdown_tasks.append(
                asyncio.create_task(self._shutdown_cafe_system())
            )

        # 모든 종료 작업 완료 대기 (타임아웃 설정)
        if shutdown_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("일부 종료 작업이 타임아웃되었습니다")
        
        # 스레드 풀 종료
        thread_pool.shutdown(wait=False, cancel_futures=True)
        
        logger.info("봇 종료 완료")

    async def _shutdown_scheduler(self):
        """스케줄러 안전 종료"""
        try:
            self.scheduler.shutdown(wait=False)
        except Exception as e:
            logger.error(f"스케줄러 종료 실패: {e}")

    async def _shutdown_bamboo_system(self):
        """대나무숲 시스템 안전 종료"""
        try:
            if hasattr(self.bamboo_system, 'close'):
                await self.bamboo_system.close()
            self.bamboo_system.shutdown()
        except Exception as e:
            logger.error(f"대나무숲 시스템 종료 실패: {e}")

# 전역 봇 매니저
bot_manager = BotManager()

# 시그널 핸들러 설정 (graceful shutdown)
def signal_handler(sig, frame):
    logger.info(f"시그널 {sig} 받음, 종료 시작...")
    asyncio.create_task(shutdown_bot())

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

async def shutdown_bot():
    """봇 안전 종료"""
    await bot_manager.shutdown()
    if not bot.is_closed():
        await bot.close()

@bot.event
async def on_ready():
    """봇 준비 완료 이벤트"""
    logger.info(f"봇이 준비되었습니다! {bot.user}로 로그인됨")
    bot_manager.reconnect_attempts = 0  # 재연결 카운터 리셋
    
    try:
        # 슬래시 명령어 동기화 (변경사항이 있을 때만)
        synced = await tree.sync()
        logger.info(f"{len(synced)}개의 명령어가 동기화되었습니다")
        
        await bot_manager.initialize()
        
    except Exception as e:
        logger.error(f"봇 시작 중 오류 발생: {e}")
        traceback.print_exc()

@bot.event
async def on_message(message):
    """메시지 이벤트 처리 (최적화)"""
    # 카페 주사위 봇은 예외 처리
    if message.author.bot and message.author.id != 218010938807287808:
        return
    
    # 비동기로 처리
    asyncio.create_task(handle_message_safe(message))

async def handle_message_safe(message):
    """안전한 메시지 처리"""
    try:
        # 카페 주사위 처리 먼저 (봇 메시지도 처리)
        cafe_handled = await handle_cafe_message(message)
        
        # 대나무숲 처리 (봇 메시지는 처리하지 않음)
        if not cafe_handled and not message.author.bot:
            await handle_message(message)
            
    except Exception as e:
        logger.error(f"메시지 처리 중 오류: {e}")

@bot.event
async def on_raw_reaction_add(payload):
    """리액션 추가 이벤트 처리 (최적화)"""
    # 봇 리액션은 빠르게 무시
    if payload.user_id == bot.user.id:
        return
    
    # 비동기로 처리
    asyncio.create_task(handle_reaction_safe(payload))

async def handle_reaction_safe(payload):
    """안전한 리액션 처리"""
    try:
        await handle_reaction(payload)
    except Exception as e:
        logger.error(f"리액션 처리 중 오류: {e}")

@bot.event
async def on_disconnect():
    """연결 끊김 이벤트"""
    logger.warning("봇 연결이 끊어졌습니다.")

@bot.event
async def on_resumed():
    """연결 재개 이벤트"""
    logger.info("봇 연결이 재개되었습니다.")
    bot_manager.reconnect_attempts = 0

@bot.event
async def on_error(event, *args, **kwargs):
    """오류 이벤트 처리"""
    logger.error(f"봇 오류 발생 - 이벤트: {event}")
    traceback.print_exc()

# === 슬래시 명령어 정의 (최적화) ===

@tree.command(name="아이템", description="러너의 아이템, 복장, 신체현황, 타락도를 확인합니다.")
async def 아이템_command(interaction: discord.Interaction):
    """아이템 확인 명령어 (최적화)"""
    # 빠른 응답을 위해 defer 사용
    await interaction.response.defer(ephemeral=True)
    
    try:
        user_id = str(interaction.user.id)
        
        # 캐시 확인
        cache_key = f"user_inventory_display:{user_id}"
        cached_display = await cache_manager.get(cache_key)
        
        if cached_display:
            await interaction.followup.send(embed=discord.Embed.from_dict(cached_display))
            return
        
        user_inventory = await get_user_inventory(user_id)

        if not user_inventory:
            await interaction.followup.send("러너 정보를 찾을 수 없습니다.")
            return

        # 데이터 포맷팅
        coins = user_inventory.get("coins", 0)
        health = user_inventory.get("health", "알 수 없음")
        items = ", ".join(user_inventory.get("items", [])) or "없음"
        outfits = ", ".join(user_inventory.get("outfits", [])) or "없음"
        physical_status = ", ".join(user_inventory.get("physical_status", [])) or "없음"
        corruption = user_inventory.get("corruption", 0)

        # 임베드 생성
        embed = discord.Embed(
            title=f"{interaction.user.display_name}님의 인벤토리",
            color=discord.Color.blue()
        )
        embed.add_field(name="💰 코인", value=str(coins), inline=True)
        embed.add_field(name="❤️ 체력", value=health, inline=True)
        embed.add_field(name="😈 타락도", value=str(corruption), inline=True)
        embed.add_field(name="🎒 아이템", value=items[:1024], inline=False)  # 필드 길이 제한
        embed.add_field(name="👕 복장", value=outfits[:1024], inline=False)
        embed.add_field(name="🏥 신체현황", value=physical_status[:1024], inline=False)

        # 캐시에 저장 (5분간)
        await cache_manager.set(cache_key, embed.to_dict(), ex=300)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.error(f"아이템 명령어 처리 실패: {e}")
        await interaction.followup.send("명령어 처리 중 오류가 발생했습니다.")

@tree.command(name="지급", description="특정 러너 또는 전체에게 아이템, 코인, 복장, 신체현황, 타락도를 지급합니다.")
async def 지급_command(interaction: discord.Interaction, 아이템: str, 유형: str, 대상: discord.Member = None):
    """지급 명령어 (최적화)"""
    await interaction.response.defer(thinking=True)
    
    try:
        success = await bot_manager.inventory_manager.process_give_command(
            interaction, 아이템, 유형, 대상
        )
        
        if not success:
            logger.warning(f"지급 실패 - 사용자: {interaction.user.id}, 아이템: {아이템}, 유형: {유형}")
            
    except Exception as e:
        logger.error(f"지급 명령어 처리 실패: {e}")
        await interaction.followup.send("명령어 처리 중 오류가 발생했습니다.", ephemeral=True)

@지급_command.autocomplete("유형")
async def 지급_유형_autocomplete(interaction: discord.Interaction, current: str):
    """지급 유형 자동완성"""
    options = ["코인", "아이템", "복장", "신체현황", "타락도"]
    return [
        app_commands.Choice(name=opt, value=opt)
        for opt in options if current.lower() in opt.lower()
    ][:25]  # Discord 제한

@tree.command(name="거래", description="코인, 아이템, 복장을 다른 유저 또는 Admin에게 거래합니다.")
async def 거래_command(interaction: discord.Interaction, 유형: str, 이름: str, 대상: discord.Member):
    """거래 명령어"""
    await interaction.response.defer()
    
    try:
        success = await bot_manager.inventory_manager.process_trade_command(
            interaction, 유형, 이름, 대상
        )
        
        if not success:
            logger.warning(f"거래 실패 - 사용자: {interaction.user.id}, 유형: {유형}, 이름: {이름}")
            
    except Exception as e:
        logger.error(f"거래 명령어 처리 실패: {e}")
        await interaction.followup.send("명령어 처리 중 오류가 발생했습니다.", ephemeral=True)

@거래_command.autocomplete("유형")
async def 거래_유형_autocomplete(interaction: discord.Interaction, current: str):
    """거래 유형 자동완성"""
    options = ["돈", "아이템", "복장"]  # 신체현황, 타락도 제외
    return [
        app_commands.Choice(name=opt, value=opt) 
        for opt in options if current in opt
    ][:25]

@거래_command.autocomplete("이름")
async def 거래_이름_autocomplete(interaction: discord.Interaction, current: str):
    """거래 이름 자동완성"""
    user_id = str(interaction.user.id)
    유형 = interaction.namespace.__dict__.get('유형')
    
    return await create_item_autocomplete_choices(user_id, 유형, current)

@tree.command(name="회수", description="특정 러너의 아이템, 복장, 신체현황, 타락도를 회수합니다.")
async def 회수_command(interaction: discord.Interaction, 대상: discord.Member, 아이템: str):
    """회수 명령어"""
    # 권한 확인 먼저
    _, can_revoke = await get_user_permissions(str(interaction.user.id))
    if not can_revoke:
        await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        target_id = str(대상.id)
        target_inventory = await bot_manager.inventory_manager.get_cached_inventory(target_id)
        
        if not target_inventory:
            await interaction.followup.send(f"{대상.display_name}님의 인벤토리를 찾을 수 없습니다.", ephemeral=True)
            return
        
        # 아이템 타입 확인
        item_type = None
        if 아이템 in target_inventory.get("items", []):
            item_type = "아이템"
        elif 아이템 in target_inventory.get("outfits", []):
            item_type = "복장"
        elif 아이템 in target_inventory.get("physical_status", []):
            item_type = "신체현황"
        elif 아이템.startswith("타락도:"):
            item_type = "타락도"
            아이템 = 아이템.split(":")[1] if ":" in 아이템 else 아이템
        else:
            item_type = "아이템"
        
        # 회수 처리
        success = await bot_manager.inventory_manager.batch_revoke_items(target_id, [아이템], item_type)
        
        if not success:
            await interaction.followup.send(f"{대상.display_name}님은 '{아이템}'을 보유하고 있지 않습니다.", ephemeral=True)
            return
        
        await interaction.followup.send(f"{대상.display_name}의 {item_type} '{아이템}'을 회수했습니다.")
        
    except Exception as e:
        logger.error(f"회수 명령어 처리 실패: {e}")
        await interaction.followup.send("명령어 처리 중 오류가 발생했습니다.", ephemeral=True)

@회수_command.autocomplete("아이템")
async def 회수_아이템_autocomplete(interaction: discord.Interaction, current: str):
    """회수 아이템 자동완성"""
    namespace = interaction.namespace
    if not hasattr(namespace, '대상') or not namespace.대상:
        return []
        
    target_id = str(namespace.대상.id)
    return await create_revoke_autocomplete_choices(target_id, current)

@tree.command(name="캐시_재갱신", description="캐싱된 데이터를 삭제하고 재갱신합니다.")
async def 캐시_재갱신_command(interaction: discord.Interaction):
    """캐시 재갱신 명령어"""
    # 권한 확인
    can_give, _ = await get_user_permissions(str(interaction.user.id))
    if not can_give:
        await interaction.response.send_message("이 명령어를 사용할 권한이 없습니다.", ephemeral=True)
        return
        
    await interaction.response.defer(ephemeral=True)
    
    try:
        # 캐시 재갱신
        await cache_daily_metadata()
        
        await interaction.followup.send("캐시가 성공적으로 재갱신되었습니다.")
        
    except Exception as e:
        logger.error(f"캐시 재갱신 실패: {e}")
        await interaction.followup.send("캐시 재갱신 중 오류가 발생했습니다.")

# === 메인 실행 부분 ===

async def main():
    """메인 실행 함수 (최적화)"""
    try:
        logger.info("봇 시작 중...")
        
        # 봇 시작 (재연결 활성화)
        async with bot:
            await bot.start(BOT_TOKEN, reconnect=True)
        
    except KeyboardInterrupt:
        logger.info("봇 종료 요청 받음")
    except discord.LoginFailure:
        logger.error("봇 토큰이 유효하지 않습니다")
    except Exception as e:
        logger.error(f"봇 실행 중 오류: {e}")
        traceback.print_exc()
    finally:
        await bot_manager.shutdown()

if __name__ == "__main__":
    try:
        # Windows 환경에서 ProactorEventLoop 사용 (성능 향상)
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("프로그램이 사용자에 의해 종료되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 치명적 오류: {e}")
        traceback.print_exc()