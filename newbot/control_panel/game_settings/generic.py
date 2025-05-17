# control_panel/game_settings/generic.py
import discord
from typing import Dict, Any

from utils.logger import log_debug, log_info, log_warning, log_error
from core.bot_config import koreanize_setting_name

class ModuleBasicSettingsModal(discord.ui.Modal):
    """모듈 기본 설정 모달"""
    
    def __init__(self, game_name, settings, bot_config):
        # 한국어 타이틀 설정
        super().__init__(title=f"{game_name} 기본 설정")
        
        self.game_name = game_name
        self.settings = settings
        self.bot_config = bot_config
        self.original_values = {}
        self.inputs = {}
        
        # 처음 5개(또는 더 적은) 설정만 추가
        count = 0
        for setting, value in settings.items():
            # 중첩 딕셔너리는 별도 처리
            if isinstance(value, dict):
                continue
                
            # 원본 값 저장
            self.original_values[setting] = value
            
            # 설정 이름을 한국어로 표시
            display_name = ' '.join(word.capitalize() for word in setting.split('_'))
            display_name = koreanize_setting_name(display_name)
            
            # 불리언 값은 "True" 또는 "False"로 표시
            if isinstance(value, bool):
                input_value = "True" if value else "False"
                help_text = "(True 또는 False 입력)"
            else:
                input_value = str(value)
                help_text = ""
            
            # TextInput 컴포넌트 생성 (모달에서는 Select를 사용할 수 없음)
            input_field = discord.ui.TextInput(
                label=f"{display_name} {help_text}",
                default=input_value,
                required=False,
                style=discord.TextStyle.short
            )
            
            self.add_item(input_field)
            self.inputs[setting] = input_field
            
            count += 1
            if count >= 5:  # 모달 항목 제한
                break
    
    async def on_submit(self, interaction: discord.Interaction):
        # 변경된 설정 처리
        changes = {}
        
        for setting, input_field in self.inputs.items():
            original_value = self.original_values[setting]
            new_value_str = input_field.value
            
            # 값 타입 변환
            if isinstance(original_value, bool):
                new_value = new_value_str.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            elif isinstance(original_value, int):
                try:
                    new_value = int(new_value_str)
                except ValueError:
                    new_value = original_value
            elif isinstance(original_value, float):
                try:
                    new_value = float(new_value_str)
                except ValueError:
                    new_value = original_value
            else:
                new_value = new_value_str
            
            # 값이 변경된 경우만 처리
            if new_value != original_value:
                changes[setting] = new_value
                # 설정 변경 내역 추적
                self.bot_config.track_change("game_settings", self.game_name, original_value, new_value, setting)
                
                # 게임 설정 업데이트
                self.bot_config.game_settings[self.game_name][setting] = new_value
        
        if changes:
            # 설정 저장
            self.bot_config.save()
            
            # 설정 적용
            # 모듈 설정 적용 함수 호출 필요 (여기서는 생략)
            
            # 변경 내역 관리자에게 보고
            from ..module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message(f"✅ {self.game_name} 모듈 기본 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
        else:
            await interaction.response.send_message("ℹ️ 변경된 설정이 없습니다.", ephemeral=True)

# 일반 게임 설정 처리 함수
async def handle_game_settings(interaction: discord.Interaction, bot, bot_config, game_name: str):
    """일반 게임 설정 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    if game_name in bot_config.game_settings:
        settings = bot_config.game_settings[game_name]
        settings_count = len([k for k, v in settings.items() if not isinstance(v, dict)])
        
        if settings_count <= 5:
            # 설정이 5개 이하면 단일 모달 사용
            modal = ModuleBasicSettingsModal(game_name, settings, bot_config)
            await interaction.response.send_modal(modal)
        else:
            # 설정이 많으면 설정 카테고리 선택 UI
            embed = discord.Embed(
                title=f"🎮 {game_name} 설정",
                description="설정 카테고리를 선택하세요.",
                color=discord.Color.green()
            )
            
            # 설정 카테고리 선택 뷰
            view = discord.ui.View(timeout=300)
            
            # 기본 설정 버튼
            basic_button = discord.ui.Button(
                style=discord.ButtonStyle.primary,
                label="기본 설정",
                custom_id=f"basic_{game_name}"
            )
            basic_button.callback = lambda i: show_game_basic_settings(i, bot, bot_config, game_name)
            view.add_item(basic_button)
            
            # 추가 설정 버튼 (설정이 5개 이상인 경우)
            if settings_count > 5:
                additional_button = discord.ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label="추가 설정",
                    custom_id=f"additional_{game_name}"
                )
                additional_button.callback = lambda i: show_game_additional_settings(i, bot, bot_config, game_name)
                view.add_item(additional_button)
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ 게임 '{game_name}'에 대한 설정이 없습니다.", ephemeral=True)

async def show_game_basic_settings(interaction, bot, bot_config, game_name):
    """게임 기본 설정 모달 표시"""
    modal = ModuleBasicSettingsModal(game_name, bot_config.game_settings[game_name], bot_config)
    await interaction.response.send_modal(modal)

class ModuleAdditionalSettingsModal(discord.ui.Modal):
    """모듈 추가 설정 모달"""
    
    def __init__(self, game_name, settings, bot_config):
        super().__init__(title=f"{game_name} 추가 설정")
        
        self.game_name = game_name
        self.settings = settings
        self.bot_config = bot_config
        self.original_values = {}
        self.inputs = {}
        
        # 5번째부터 10번째(또는 마지막)까지의 설정만 추가
        count = 0
        for setting, value in settings.items():
            # 중첩 딕셔너리는 별도 처리
            if isinstance(value, dict):
                continue
                
            count += 1
            if count <= 5:  # 처음 5개는 기본 설정에서 처리
                continue
                
            # 원본 값 저장
            self.original_values[setting] = value
            
            # 설정 이름을 한국어로 표시
            display_name = ' '.join(word.capitalize() for word in setting.split('_'))
            display_name = koreanize_setting_name(display_name)
            
            # 불리언 값은 "True" 또는 "False"로 표시
            if isinstance(value, bool):
                input_value = "True" if value else "False"
                help_text = "(True 또는 False 입력)"
            else:
                input_value = str(value)
                help_text = ""
            
            # TextInput 컴포넌트 생성
            input_field = discord.ui.TextInput(
                label=f"{display_name} {help_text}",
                default=input_value,
                required=False,
                style=discord.TextStyle.short
            )
            
            self.add_item(input_field)
            self.inputs[setting] = input_field
            
            if len(self.inputs) >= 5:  # 모달 항목 제한
                break
    
    async def on_submit(self, interaction: discord.Interaction):
        # ModuleBasicSettingsModal과 동일한 처리 로직
        changes = {}
        
        for setting, input_field in self.inputs.items():
            original_value = self.original_values[setting]
            new_value_str = input_field.value
            
            # 값 타입 변환
            if isinstance(original_value, bool):
                new_value = new_value_str.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            elif isinstance(original_value, int):
                try:
                    new_value = int(new_value_str)
                except ValueError:
                    new_value = original_value
            elif isinstance(original_value, float):
                try:
                    new_value = float(new_value_str)
                except ValueError:
                    new_value = original_value
            else:
                new_value = new_value_str
            
            # 값이 변경된 경우만 처리
            if new_value != original_value:
                changes[setting] = new_value
                # 설정 변경 내역 추적
                self.bot_config.track_change("game_settings", self.game_name, original_value, new_value, setting)
                
                # 게임 설정 업데이트
                self.bot_config.game_settings[self.game_name][setting] = new_value
        
        if changes:
            # 설정 저장
            self.bot_config.save()
            
            # 설정 적용
            # 모듈 설정 적용 함수 호출 필요 (여기서는 생략)
            
            # 변경 내역 관리자에게 보고
            from ..module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message(f"✅ {self.game_name} 모듈 추가 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
        else:
            await interaction.response.send_message("ℹ️ 변경된 설정이 없습니다.", ephemeral=True)

async def show_game_additional_settings(interaction, bot, bot_config, game_name):
    """게임 추가 설정 모달 표시"""
    modal = ModuleAdditionalSettingsModal(game_name, bot_config.game_settings[game_name], bot_config)
    await interaction.response.send_modal(modal)