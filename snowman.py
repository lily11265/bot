# snowman.py
import discord
import asyncio
import random
import json
import os
from typing import Dict, List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class GamePhase(Enum):
    ROLLING = "굴리기"
    STACKING = "쌓기"
    FINISHED = "완료"

class Direction(Enum):
    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

@dataclass
class SnowBall:
    size: int
    position: Tuple[int, int]  # 쌓기 단계에서의 위치 (x좌표)
    
@dataclass
class LeaderboardEntry:
    user_id: int
    username: str
    score: int
    height: int
    timestamp: datetime

class SnowmanGame:
    def __init__(self):
        self.active_games = {}
        self.leaderboard_file = "snowman_leaderboard.json"
        
        # 게임 설정
        self.FIELD_SIZE = 10
        self.OBSTACLE_COUNT = 6
        self.MAX_FAILURES = 3
        
        # 쌓기 단계 설정
        self.STACK_WIDTH = 15  # 쌓기 바의 너비
        self.MOVE_SPEED = 0.5  # 검정 타일 이동 속도
        self.STABILITY_THRESHOLD = 4  # 안정성 임계값
    
    async def start_game(self, interaction: discord.Interaction):
        """게임 시작"""
        user_id = interaction.user.id
        channel_id = interaction.channel_id
        
        if channel_id in self.active_games:
            await interaction.response.send_message(
                "이미 진행 중인 눈사람 게임이 있습니다!",
                ephemeral=True
            )
            return
        
        # 게임 데이터 초기화
        game_data = {
            "user": interaction.user,
            "phase": GamePhase.ROLLING,
            "field": self._create_field(),
            "position": (5, 5),  # 시작 위치 (중앙)
            "direction": Direction.RIGHT,
            "trail": [(5, 5)],  # 지나온 길
            "snowball_size": 1,
            "failures": 0,
            "snowballs": [],  # 완성된 눈공들
            "current_height": 0,
            "stacking_position": 7,  # 쌓기 단계에서 움직이는 위치
            "stacking_direction": 1,  # 1: 오른쪽, -1: 왼쪽
            "base_positions": [],  # 각 층의 눈공 위치들
            "stability": 0,  # 눈사람 안정성
            "moving": True
        }
        
        self.active_games[channel_id] = game_data
        
        # 첫 화면 표시
        embed = self._create_embed(game_data)
        await interaction.response.send_message(embed=embed)
        
        # 메시지 가져오기 및 리액션 추가
        message = await interaction.original_response()
        game_data["message"] = message
        
        # 리액션 추가
        reactions = ["⬆️", "⬇️", "⬅️", "➡️", "🔴"]
        for reaction in reactions:
            await message.add_reaction(reaction)
        
        # 이동 태스크 시작
        game_data["move_task"] = asyncio.create_task(self._auto_move(channel_id))
        
        # 리액션 리스너 등록
        self._add_reaction_listener(channel_id)
    
    async def start_game_direct(self, channel, user):
        """채널에 직접 게임 시작 (defer된 인터랙션용)"""
        channel_id = channel.id
        
        if channel_id in self.active_games:
            await channel.send("이미 진행 중인 눈사람 게임이 있습니다!")
            return
        
        # 게임 데이터 초기화
        game_data = {
            "user": user,
            "phase": GamePhase.ROLLING,
            "field": self._create_field(),
            "position": (5, 5),
            "direction": Direction.RIGHT,
            "trail": [(5, 5)],
            "snowball_size": 1,
            "failures": 0,
            "snowballs": [],
            "current_height": 0,
            "stacking_position": 7,
            "stacking_direction": 1,
            "base_positions": [],
            "stability": 0,
            "moving": True
        }
        
        self.active_games[channel_id] = game_data
        
        # 첫 화면 표시
        embed = self._create_embed(game_data)
        message = await channel.send(embed=embed)
        game_data["message"] = message
        
        # 리액션 추가
        reactions = ["⬆️", "⬇️", "⬅️", "➡️", "🔴"]
        for reaction in reactions:
            await message.add_reaction(reaction)
        
        # 이동 태스크 시작
        game_data["move_task"] = asyncio.create_task(self._auto_move(channel_id))
        
        # 리액션 리스너 등록
        self._add_reaction_listener(channel_id)
    
    def _create_field(self) -> List[List[str]]:
        """게임 필드 생성"""
        # 모든 칸을 눈(⚪)으로 채움
        field = [["⚪" for _ in range(self.FIELD_SIZE)] for _ in range(self.FIELD_SIZE)]
        
        # 장애물 배치
        obstacles_placed = 0
        while obstacles_placed < self.OBSTACLE_COUNT:
            x, y = random.randint(0, self.FIELD_SIZE-1), random.randint(0, self.FIELD_SIZE-1)
            
            # 시작 위치(5,5) 주변은 피함
            if abs(x - 5) <= 1 and abs(y - 5) <= 1:
                continue
            
            if field[x][y] == "⚪":
                field[x][y] = "🌲"  # 나무 장애물
                obstacles_placed += 1
        
        return field
    
    def _create_embed(self, game_data) -> discord.Embed:
        """게임 화면 임베드 생성"""
        if game_data["phase"] == GamePhase.ROLLING:
            return self._create_rolling_embed(game_data)
        elif game_data["phase"] == GamePhase.STACKING:
            return self._create_stacking_embed(game_data)
        else:
            return self._create_result_embed(game_data)
    
    def _create_rolling_embed(self, game_data) -> discord.Embed:
        """굴리기 단계 임베드"""
        embed = discord.Embed(
            title="❄️ 눈사람 만들기 - 눈 굴리기",
            description="방향키로 눈을 굴려 크게 만들어보세요!",
            color=discord.Color.blue()
        )
        
        # 필드 표시
        field_str = ""
        pos_x, pos_y = game_data["position"]
        
        for i in range(self.FIELD_SIZE):
            row = ""
            for j in range(self.FIELD_SIZE):
                if (i, j) == (pos_x, pos_y):
                    row += "🔵"  # 플레이어 위치
                elif (i, j) in game_data["trail"]:
                    row += "❄️"  # 지나온 길
                else:
                    row += game_data["field"][i][j]
            field_str += row + "\n"
        
        embed.add_field(
            name="게임 필드",
            value=f"```\n{field_str}```",
            inline=False
        )
        
        # 게임 정보
        info = f"눈공 크기: **{game_data['snowball_size']}**\n"
        info += f"현재 높이: **{game_data['current_height']}층**\n"
        if game_data["snowballs"]:
            last_ball = game_data["snowballs"][-1]
            info += f"마지막 눈공: 크기 {last_ball.size}"
        
        embed.add_field(
            name="상태",
            value=info,
            inline=True
        )
        
        # 조작 안내
        controls = "⬆️ 위로\n⬇️ 아래로\n⬅️ 왼쪽으로\n➡️ 오른쪽으로\n🔴 그만 굴리기"
        embed.add_field(
            name="조작법",
            value=controls,
            inline=True
        )
        
        # 실패 횟수
        embed.add_field(
            name="실패 횟수",
            value=f"{game_data['failures']}/{self.MAX_FAILURES}",
            inline=True
        )
        
        return embed
    
    def _create_stacking_embed(self, game_data) -> discord.Embed:
        """쌓기 단계 임베드"""
        embed = discord.Embed(
            title="🏗️ 눈사람 만들기 - 쌓아올리기",
            description=f"크기 {game_data['snowball_size']}의 눈공을 쌓아올리세요!",
            color=discord.Color.green()
        )
        
        # 쌓기 바 표시
        bar = ["⬜"] * self.STACK_WIDTH
        bar[game_data["stacking_position"]] = "⬛"
        
        # 이전 눈공들의 위치 표시
        if game_data["base_positions"]:
            for pos_list in game_data["base_positions"]:
                for pos in pos_list:
                    if 0 <= pos < self.STACK_WIDTH:
                        if bar[pos] == "⬜":
                            bar[pos] = "🔘"
                        else:
                            bar[pos] = "🔴"  # 겹치는 위치
        
        bar_str = "".join(bar)
        
        embed.add_field(
            name="타이밍 바",
            value=f"`{bar_str}`\n🔴를 눌러 눈공을 놓으세요!",
            inline=False
        )
        
        # 눈사람 상태
        info = f"현재 높이: **{game_data['current_height']}층**\n"
        info += f"놓을 눈공 크기: **{game_data['snowball_size']}**\n"
        info += f"안정성: {'🟢' if game_data['stability'] < 3 else '🟡' if game_data['stability'] < 6 else '🔴'}"
        
        embed.add_field(
            name="상태",
            value=info,
            inline=False
        )
        
        return embed
    
    def _create_result_embed(self, game_data) -> discord.Embed:
        """결과 화면 임베드"""
        embed = discord.Embed(
            title="🎉 눈사람 완성!",
            description=f"{game_data['user'].display_name}님의 눈사람",
            color=discord.Color.gold()
        )
        
        # 최종 점수 계산
        total_score = sum(ball.size for ball in game_data["snowballs"]) * game_data["current_height"]
        
        embed.add_field(
            name="최종 결과",
            value=f"높이: **{game_data['current_height']}층**\n"
                  f"총 점수: **{total_score}점**",
            inline=False
        )
        
        # 사용된 눈공들
        if game_data["snowballs"]:
            balls_info = "\n".join([
                f"{i+1}층: 크기 {ball.size}" 
                for i, ball in enumerate(game_data["snowballs"])
            ])
            embed.add_field(
                name="눈공 구성",
                value=balls_info,
                inline=True
            )
        
        return embed
    
    def _add_reaction_listener(self, channel_id: int):
        """리액션 리스너 등록"""
        def check(reaction, user):
            game_data = self.active_games.get(channel_id)
            if not game_data:
                return False
            
            return (
                reaction.message.id == game_data["message"].id and
                user.id == game_data["user"].id and
                str(reaction.emoji) in ["⬆️", "⬇️", "⬅️", "➡️", "🔴"]
            )
        
        # 비동기 태스크로 리액션 대기
        asyncio.create_task(self._wait_for_reaction(channel_id, check))
    
    async def _wait_for_reaction(self, channel_id: int, check):
        """리액션 대기"""
        try:
            while channel_id in self.active_games:
                try:
                    reaction, user = await asyncio.wait_for(
                        self.active_games[channel_id]["message"].bot.wait_for('reaction_add', check=check),
                        timeout=1.0
                    )
                    
                    # 리액션 처리
                    await self._handle_reaction(channel_id, str(reaction.emoji))
                    
                    # 리액션 제거
                    try:
                        await reaction.remove(user)
                    except:
                        pass
                        
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Reaction error: {e}")
                    break
        except Exception as e:
            logger.error(f"Reaction listener error: {e}")
    
    async def _handle_reaction(self, channel_id: int, emoji: str):
        """리액션 처리"""
        game_data = self.active_games.get(channel_id)
        if not game_data:
            return
        
        if game_data["phase"] == GamePhase.ROLLING:
            await self._handle_rolling_reaction(channel_id, emoji)
        elif game_data["phase"] == GamePhase.STACKING:
            await self._handle_stacking_reaction(channel_id, emoji)
    
    async def _handle_rolling_reaction(self, channel_id: int, emoji: str):
        """굴리기 단계 리액션 처리"""
        game_data = self.active_games[channel_id]
        
        if emoji == "🔴":
            # 그만 굴리기 - 쌓기 단계로 전환
            await self._switch_to_stacking(channel_id)
        else:
            # 방향 변경
            direction_map = {
                "⬆️": Direction.UP,
                "⬇️": Direction.DOWN,
                "⬅️": Direction.LEFT,
                "➡️": Direction.RIGHT
            }
            
            if emoji in direction_map:
                game_data["direction"] = direction_map[emoji]
    
    async def _handle_stacking_reaction(self, channel_id: int, emoji: str):
        """쌓기 단계 리액션 처리"""
        if emoji == "🔴":
            await self._place_snowball(channel_id)
    
    async def _auto_move(self, channel_id: int):
        """자동 이동 처리"""
        while channel_id in self.active_games:
            game_data = self.active_games[channel_id]
            
            try:
                if game_data["phase"] == GamePhase.ROLLING and game_data["moving"]:
                    await self._move_player(channel_id)
                elif game_data["phase"] == GamePhase.STACKING:
                    await self._move_stacking_cursor(channel_id)
                
                await asyncio.sleep(0.8 if game_data["phase"] == GamePhase.ROLLING else 0.3)
                
            except Exception as e:
                logger.error(f"Auto move error: {e}")
                break
    
    async def _move_player(self, channel_id: int):
        """플레이어 이동"""
        game_data = self.active_games[channel_id]
        
        dx, dy = game_data["direction"].value
        current_x, current_y = game_data["position"]
        new_x, new_y = current_x + dx, current_y + dy
        
        # 경계 체크
        if not (0 <= new_x < self.FIELD_SIZE and 0 <= new_y < self.FIELD_SIZE):
            await self._handle_collision(channel_id)
            return
        
        # 장애물 체크
        if game_data["field"][new_x][new_y] == "🌲":
            await self._handle_collision(channel_id)
            return
        
        # 이미 지나온 길 체크
        if (new_x, new_y) in game_data["trail"]:
            await self._handle_collision(channel_id)
            return
        
        # 이동 성공
        game_data["position"] = (new_x, new_y)
        game_data["trail"].append((new_x, new_y))
        
        # 눈공 크기 증가 (눈을 굴림)
        if game_data["field"][new_x][new_y] == "⚪":
            game_data["snowball_size"] += 1
        
        # 화면 업데이트
        await self._update_display(channel_id)
    
    async def _move_stacking_cursor(self, channel_id: int):
        """쌓기 단계 커서 이동"""
        game_data = self.active_games[channel_id]
        
        game_data["stacking_position"] += game_data["stacking_direction"]
        
        # 경계에서 방향 전환
        if game_data["stacking_position"] <= 0:
            game_data["stacking_position"] = 0
            game_data["stacking_direction"] = 1
        elif game_data["stacking_position"] >= self.STACK_WIDTH - 1:
            game_data["stacking_position"] = self.STACK_WIDTH - 1
            game_data["stacking_direction"] = -1
        
        # 화면 업데이트
        await self._update_display(channel_id)
    
    async def _handle_collision(self, channel_id: int):
        """충돌 처리"""
        game_data = self.active_games[channel_id]
        game_data["failures"] += 1
        
        if game_data["failures"] >= self.MAX_FAILURES:
            # 게임 오버
            await self._end_game(channel_id)
        else:
            # 다시 시작
            game_data["field"] = self._create_field()
            game_data["position"] = (5, 5)
            game_data["direction"] = Direction.RIGHT
            game_data["trail"] = [(5, 5)]
            game_data["snowball_size"] = 1
            
            await self._update_display(channel_id)
    
    async def _switch_to_stacking(self, channel_id: int):
        """쌓기 단계로 전환"""
        game_data = self.active_games[channel_id]
        
        # 현재 눈공을 완성된 것으로 추가
        if game_data["snowball_size"] > 1:
            snowball = SnowBall(
                size=game_data["snowball_size"],
                position=(7,)  # 초기 중앙 위치
            )
            game_data["snowballs"].append(snowball)
            game_data["current_height"] += 1
        
        game_data["phase"] = GamePhase.STACKING
        game_data["moving"] = False  # 자동 이동 정지
        
        await self._update_display(channel_id)
    
    async def _place_snowball(self, channel_id: int):
        """눈공 배치"""
        game_data = self.active_games[channel_id]
        current_pos = game_data["stacking_position"]
        
        # 배치 가능 여부 확인
        if game_data["current_height"] > 0:
            last_positions = game_data["base_positions"][-1] if game_data["base_positions"] else []
            
            # 이전 눈공과의 거리 체크
            if last_positions:
                min_distance = min(abs(current_pos - pos) for pos in last_positions)
                if min_distance > 3:  # 너무 멀리 떨어져 있으면
                    game_data["stability"] += 2
                    if game_data["stability"] >= self.STABILITY_THRESHOLD * 2:
                        # 눈사람 무너짐
                        await self._end_game(channel_id)
                        return
        
        # 눈공 배치 성공
        ball_positions = []
        size = game_data["snowball_size"]
        
        # 눈공 크기에 따라 차지하는 위치 계산
        for i in range(max(1, size // 3)):
            pos = current_pos + i - size // 6
            if 0 <= pos < self.STACK_WIDTH:
                ball_positions.append(pos)
        
        game_data["base_positions"].append(ball_positions)
        
        # 다음 눈공 준비
        game_data["field"] = self._create_field()
        game_data["position"] = (5, 5)
        game_data["direction"] = Direction.RIGHT
        game_data["trail"] = [(5, 5)]
        game_data["snowball_size"] = 1
        game_data["phase"] = GamePhase.ROLLING
        game_data["moving"] = True
        
        await self._update_display(channel_id)
    
    async def _update_display(self, channel_id: int):
        """화면 업데이트"""
        game_data = self.active_games.get(channel_id)
        if not game_data or not game_data.get("message"):
            return
        
        try:
            embed = self._create_embed(game_data)
            await game_data["message"].edit(embed=embed)
        except Exception as e:
            logger.error(f"Display update error: {e}")
    
    async def _end_game(self, channel_id: int):
        """게임 종료"""
        game_data = self.active_games.get(channel_id)
        if not game_data:
            return
        
        # 이동 태스크 정리
        if "move_task" in game_data:
            game_data["move_task"].cancel()
        
        game_data["phase"] = GamePhase.FINISHED
        
        # 최종 점수 계산
        total_score = sum(ball.size for ball in game_data["snowballs"]) * game_data["current_height"]
        
        # 리더보드 업데이트
        guild_id = game_data["message"].guild.id if game_data.get("message") else 0
        await self._update_leaderboard(guild_id, game_data["user"], total_score, game_data["current_height"])
        
        # 최종 결과 표시
        result_embed = self._create_result_embed(game_data)
        
        # 리더보드 추가
        leaderboard_text = await self._get_leaderboard_text(guild_id, game_data["user"].id)
        if leaderboard_text:
            result_embed.add_field(
                name="🏆 서버 리더보드",
                value=leaderboard_text,
                inline=False
            )
        
        await game_data["message"].edit(embed=result_embed, view=None)
        
        # 리액션 정리
        try:
            await game_data["message"].clear_reactions()
        except:
            pass
        
        # 게임 데이터 정리
        del self.active_games[channel_id]
    
    async def _update_leaderboard(self, guild_id: int, user: discord.Member, score: int, height: int):
        """리더보드 업데이트"""
        leaderboard = self._load_leaderboard()
        
        guild_key = str(guild_id)
        if guild_key not in leaderboard:
            leaderboard[guild_key] = {}
        
        user_key = str(user.id)
        current_entry = leaderboard[guild_key].get(user_key)
        
        # 최고 점수만 저장
        if not current_entry or score > current_entry["score"]:
            leaderboard[guild_key][user_key] = {
                "username": user.display_name,
                "score": score,
                "height": height,
                "timestamp": datetime.now().isoformat()
            }
            
            self._save_leaderboard(leaderboard)
    
    async def _get_leaderboard_text(self, guild_id: int, user_id: int) -> str:
        """리더보드 텍스트 생성"""
        leaderboard = self._load_leaderboard()
        guild_key = str(guild_id)
        
        if guild_key not in leaderboard:
            return "아직 기록이 없습니다."
        
        # 점수순으로 정렬
        entries = []
        for uid, data in leaderboard[guild_key].items():
            entries.append((int(uid), data["username"], data["score"], data["height"]))
        
        entries.sort(key=lambda x: x[2], reverse=True)  # 점수순 정렬
        
        if not entries:
            return "아직 기록이 없습니다."
        
        # 상위 5명
        result = []
        for i, (uid, username, score, height) in enumerate(entries[:5]):
            medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
            result.append(f"{medal} {username}: {score}점 ({height}층)")
        
        # 현재 유저 순위
        user_rank = None
        for i, (uid, username, score, height) in enumerate(entries):
            if uid == user_id:
                user_rank = i + 1
                break
        
        if user_rank and user_rank > 5:
            result.append(f"...")
            result.append(f"{user_rank}위: 당신의 기록")
        
        return "\n".join(result)
    
    def _load_leaderboard(self) -> Dict:
        """리더보드 로드"""
        if os.path.exists(self.leaderboard_file):
            try:
                with open(self.leaderboard_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load leaderboard: {e}")
        return {}
    
    def _save_leaderboard(self, leaderboard: Dict):
        """리더보드 저장"""
        try:
            with open(self.leaderboard_file, 'w', encoding='utf-8') as f:
                json.dump(leaderboard, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save leaderboard: {e}")

# 전역 게임 인스턴스
snowman_game = SnowmanGame()

def get_snowman_game():
    return snowman_game