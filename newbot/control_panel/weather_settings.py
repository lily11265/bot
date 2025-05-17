# control_panel/weather_settings.py
import discord
import os
import json
from utils.logger import log_debug, log_info, log_warning, log_error
from utils.helpers import safe_float_convert

class WeatherBasicSettingsModal(discord.ui.Modal, title="날씨 시스템 기본 설정"):
    def __init__(self, bot_config):
        super().__init__()
        self.bot_config = bot_config
        
        # 설정 항목들 - TextInput만 사용
        self.enable_weather_system = discord.ui.TextInput(
            label="날씨 시스템 활성화 (True/False)",
            default="True" if bot_config.weather_settings.get("enable_weather_system", True) else "False",
            required=True
        )
        self.add_item(self.enable_weather_system)
        
        self.enable_channel_specific_weather = discord.ui.TextInput(
            label="채널별 날씨 활성화 (True/False)",
            default="True" if bot_config.weather_settings.get("enable_channel_specific_weather", False) else "False",
            required=True
        )
        self.add_item(self.enable_channel_specific_weather)
        
        self.horror_mode_probability = discord.ui.TextInput(
            label="공포모드 확률(%)",
            default=str(bot_config.weather_settings.get("horror_mode_probability", 5.0)),
            required=True
        )
        self.add_item(self.horror_mode_probability)
        
        self.unique_item_probability = discord.ui.TextInput(
            label="유니크 아이템 확률(%)",
            default=str(bot_config.weather_settings.get("unique_item_probability", 5.0)),
            required=True
        )
        self.add_item(self.unique_item_probability)
        
        self.notify_weather_changes = discord.ui.TextInput(
            label="날씨 변경 알림 (True/False)",
            default="True" if bot_config.weather_settings.get("notify_weather_changes", True) else "False",
            required=True
        )
        self.add_item(self.notify_weather_changes)
    
    async def on_submit(self, interaction: discord.Interaction):
        # 원래 값 저장
        old_settings = self.bot_config.weather_settings.copy()
        
        # 입력값 파싱
        try:
            # utility.py의 safe_float_convert 함수 사용
            new_settings = {
                "enable_weather_system": self.enable_weather_system.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"],
                "enable_channel_specific_weather": self.enable_channel_specific_weather.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"],
                "horror_mode_probability": safe_float_convert(self.horror_mode_probability.value, 5.0),
                "unique_item_probability": safe_float_convert(self.unique_item_probability.value, 5.0),
                "notify_weather_changes": self.notify_weather_changes.value.lower() in ["true", "1", "yes", "y", "on", "참", "예"]
            }
            
            # 범위 검사
            if new_settings["horror_mode_probability"] < 0 or new_settings["horror_mode_probability"] > 100:
                raise ValueError("공포모드 확률은 0에서 100 사이여야 합니다.")
            if new_settings["unique_item_probability"] < 0 or new_settings["unique_item_probability"] > 100:
                raise ValueError("유니크 아이템 확률은 0에서 100 사이여야 합니다.")
            
            # 변경 사항 추적
            for key, new_value in new_settings.items():
                old_value = old_settings[key]
                if old_value != new_value:
                    self.bot_config.track_change("weather_settings", key, old_value, new_value)
            
            # 설정 업데이트
            self.bot_config.weather_settings.update(new_settings)
            
            # 설정 저장
            self.bot_config.save()
            
            # 날씨 시스템에 설정 적용
            try:
                import file.weather
                if hasattr(file.weather, 'GLOBAL_SETTINGS'):
                    file.weather.GLOBAL_SETTINGS['ENABLE_WEATHER_SYSTEM'] = new_settings['enable_weather_system']
                    file.weather.GLOBAL_SETTINGS['ENABLE_CHANNEL_SPECIFIC_WEATHER'] = new_settings['enable_channel_specific_weather']
                    file.weather.GLOBAL_SETTINGS['HORROR_MODE_PROBABILITY'] = new_settings['horror_mode_probability']
                    file.weather.GLOBAL_SETTINGS['UNIQUE_ITEM_PROBABILITY'] = new_settings['unique_item_probability']
                    file.weather.GLOBAL_SETTINGS['NOTIFY_WEATHER_CHANGES'] = new_settings['notify_weather_changes']
            except ImportError:
                log_warning("날씨 모듈을 가져올 수 없습니다. 설정만 저장됨.")
            
            # 변경 내역 관리자에게 보고
            from .module_views import notify_admins_about_changes
            await notify_admins_about_changes(interaction.client, self.bot_config)
            
            await interaction.response.send_message("✅ 날씨 시스템 설정이 업데이트되었습니다.", ephemeral=True)
            self.bot_config.clear_changes()
        except ValueError as e:
            await interaction.response.send_message(f"⚠️ 입력 오류: {str(e)}", ephemeral=True)
        except Exception as e:
            log_error(f"날씨 설정 업데이트 중 오류 발생: {e}", e)
            await interaction.response.send_message(f"⚠️ 오류 발생: {str(e)}", ephemeral=True)

class WeatherChannelSelectorView(discord.ui.View):
    def __init__(self, guild, bot_config):
        super().__init__(timeout=300)
        self.guild = guild
        self.bot_config = bot_config
        self.current_page = 0
        self.channels_per_page = 25  # Discord 드롭다운 최대 25개 제한
        self.all_channels = [channel for channel in guild.text_channels]
        
        # 날씨 모듈 가져오기
        try:
            import file.weather
            self.global_settings = file.weather.GLOBAL_SETTINGS
        except ImportError:
            self.global_settings = {"ANNOUNCEMENT_CHANNEL_NAME": ""}
        
        # 초기 채널 목록 추가
        self.update_channel_select()
        
        # 검색 버튼 추가
        search_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="검색",
            emoji="🔍"
        )
        search_button.callback = self.on_search
        self.add_item(search_button)
    
    def update_channel_select(self, search_query=None):
        # 기존 드롭다운 제거
        for item in self.children[:]:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        
        # 채널 필터링
        filtered_channels = self.all_channels
        if search_query:
            filtered_channels = [c for c in self.all_channels if search_query.lower() in c.name.lower()]
        
        # 페이지 계산
        start_idx = self.current_page * self.channels_per_page
        end_idx = min(start_idx + self.channels_per_page, len(filtered_channels))
        
        # 현재 페이지의 채널 가져오기
        current_channels = filtered_channels[start_idx:end_idx]
        
        if not current_channels:
            # 채널이 없으면 메시지 추가
            return False
        
        # 드롭다운 옵션 생성
        options = []
        for channel in current_channels:
            options.append(discord.SelectOption(
                label=channel.name,
                value=str(channel.id),
                default=channel.name == self.global_settings.get("ANNOUNCEMENT_CHANNEL_NAME", "")
            ))
        
        # 새 드롭다운 추가
        channel_select = discord.ui.Select(
            placeholder="날씨 공지 채널 선택",
            options=options
        )
        channel_select.callback = self.on_channel_select
        self.add_item(channel_select)
        
        return True
    
    async def on_search(self, interaction):
        # 검색 모달 표시
        modal = discord.ui.Modal(title="채널 검색")
        search_input = discord.ui.TextInput(
            label="채널 이름 검색",
            placeholder="검색할 채널 이름 입력"
        )
        modal.add_item(search_input)
        
        async def on_modal_submit(interaction):
            self.current_page = 0  # 페이지 초기화
            has_channels = self.update_channel_select(search_input.value)
            
            if has_channels:
                await interaction.response.edit_message(content=f"'{search_input.value}' 검색 결과:", view=self)
            else:
                await interaction.response.edit_message(content=f"'{search_input.value}' 검색 결과가 없습니다.", view=self)
        
        modal.on_submit = on_modal_submit
        await interaction.response.send_modal(modal)
    
    async def on_channel_select(self, interaction):
        try:
            # 선택한 채널 ID로 채널 객체 가져오기
            channel_id = int(interaction.data["values"][0])
            channel = interaction.guild.get_channel(channel_id)
            
            if channel:
                # 날씨 모듈에 설정 적용
                try:
                    import file.weather
                    file.weather.GLOBAL_SETTINGS["ANNOUNCEMENT_CHANNEL_NAME"] = channel.name
                    
                    # 설정 저장
                    weather_cog = interaction.client.get_cog('WeatherCommands')
                    if weather_cog and hasattr(weather_cog, 'weather_system'):
                        weather_cog.weather_system.save_settings()
                except ImportError:
                    log_warning("날씨 모듈을 가져올 수 없습니다. 설정만 저장됨.")
                
                # bot_config에도 저장
                self.bot_config.weather_settings["announcement_channel_name"] = channel.name
                self.bot_config.save()
                
                await interaction.response.send_message(f"✅ 날씨 공지 채널이 '{channel.name}'(으)로 설정되었습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ 선택한 채널을 찾을 수 없습니다.", ephemeral=True)
        except Exception as e:
            log_error(f"채널 설정 저장 중 오류 발생: {e}", e)
            await interaction.response.send_message(f"⚠️ 오류 발생: {str(e)}", ephemeral=True)

class WeatherChannelGroupModal(discord.ui.Modal):
    def __init__(self, group_name, bot_config):
        super().__init__(title=f"날씨 시스템 {group_name} 설정")
        self.group_name = group_name
        self.bot_config = bot_config
        
        # 날씨 모듈 가져오기
        try:
            import file.weather
            self.channel_groups = file.weather.CHANNEL_GROUPS
        except ImportError:
            self.channel_groups = {}
        
        # 현재 설정된 채널 ID 문자열로 변환
        current_channel_ids = ", ".join(self.channel_groups.get(group_name, set()))
        
        # 서버 ID 필드
        self.server_id = discord.ui.TextInput(
            label="서버 ID",
            placeholder="현재 서버 ID가 자동으로 사용됩니다.",
            required=False
        )
        self.add_item(self.server_id)
        
        # 카테고리 필드
        self.categories = discord.ui.TextInput(
            label="카테고리 (이름, 쉼표로 구분)",
            placeholder="예: 마을, 진행, 시스템",
            required=False,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.categories)
        
        # 채널 ID 필드
        self.channel_ids = discord.ui.TextInput(
            label="채널 ID (쉼표로 구분)",
            placeholder="예: 123456789, 987654321",
            default=current_channel_ids,
            required=False,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.channel_ids)
        
        # 스레드 ID 필드
        self.thread_ids = discord.ui.TextInput(
            label="스레드 ID (쉼표로 구분)",
            placeholder="예: 123456789, 987654321",
            required=False,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.thread_ids)
        
        # 도움말 필드
        help_text = """
ID 찾기: 
채널 우클릭 -> '링크 복사' -> 마지막 숫자
예: https://discord.com/channels/123456/789012
ID: 789012
"""
        self.help_text = discord.ui.TextInput(
            label="도움말",
            default=help_text,
            required=False,
            style=discord.TextStyle.paragraph
        )
        self.add_item(self.help_text)
    
    async def on_submit(self, interaction):
        try:
            # 날씨 모듈 가져오기
            import file.weather
            
            # 새로운 채널 ID 세트 생성
            new_channel_ids = set()
            
            # 서버 ID 처리 (비어있으면 현재 서버 ID 사용)
            server_id = self.server_id.value.strip()
            if not server_id:
                server_id = str(interaction.guild.id)
            else:
                # 유효성 검사
                if not server_id.isdigit():
                    await interaction.response.send_message("⚠️ 유효하지 않은 서버 ID입니다. 숫자만 입력해주세요.", ephemeral=True)
                    return
            
            # 카테고리 처리
            if self.categories.value.strip():
                category_names = [name.strip() for name in self.categories.value.split(',') if name.strip()]
                category_found = False
                
                for category_name in category_names:
                    for category in interaction.guild.categories:
                        if category_name.lower() in category.name.lower():
                            category_found = True
                            # 카테고리의 모든 채널 추가
                            for channel in category.channels:
                                new_channel_ids.add(str(channel.id))
                
                if category_names and not category_found:
                    await interaction.response.send_message("⚠️ 입력한 카테고리 이름과 일치하는 카테고리를 찾을 수 없습니다.", ephemeral=True)
                    return
            
            # 채널 ID 처리
            invalid_channel_ids = []
            if self.channel_ids.value.strip():
                channel_id_list = [cid.strip() for cid in self.channel_ids.value.split(',') if cid.strip()]
                for channel_id in channel_id_list:
                    # 숫자인지 확인
                    if channel_id.isdigit():
                        new_channel_ids.add(channel_id)
                    else:
                        invalid_channel_ids.append(channel_id)
            
            # 스레드 ID 처리
            invalid_thread_ids = []
            if self.thread_ids.value.strip():
                thread_id_list = [tid.strip() for tid in self.thread_ids.value.split(',') if tid.strip()]
                for thread_id in thread_id_list:
                    # 숫자인지 확인
                    if thread_id.isdigit():
                        new_channel_ids.add(thread_id)
                    else:
                        invalid_thread_ids.append(thread_id)
            
            # 유효하지 않은 ID 경고
            warnings = []
            if invalid_channel_ids:
                warnings.append(f"⚠️ 유효하지 않은 채널 ID: {', '.join(invalid_channel_ids)}")
            if invalid_thread_ids:
                warnings.append(f"⚠️ 유효하지 않은 스레드 ID: {', '.join(invalid_thread_ids)}")
            
            # 날씨 시스템 설정 업데이트
            file.weather.CHANNEL_GROUPS[self.group_name] = new_channel_ids
            
            # 설정 저장
            weather_cog = interaction.client.get_cog('WeatherCommands')
            if weather_cog and hasattr(weather_cog, 'weather_system'):
                # 날씨 시스템에 채널 그룹 저장 메서드 추가
                if hasattr(weather_cog.weather_system, 'save_settings'):
                    weather_cog.weather_system.save_settings()
            
            # bot_config에도 저장 (채널 그룹 구조는 복잡해서 직접 저장하지는 않음)
            
            # 응답 메시지 구성
            message = f"✅ {self.group_name} 채널 그룹 설정이 저장되었습니다. (총 {len(new_channel_ids)}개 채널/스레드)"
            if warnings:
                message += "\n" + "\n".join(warnings)
            
            await interaction.response.send_message(message, ephemeral=True)
        except Exception as e:
            log_error(f"채널 그룹 설정 저장 중 오류 발생: {e}", e)
            await interaction.response.send_message(f"⚠️ 오류 발생: {str(e)}", ephemeral=True)

class WeatherSettingsView(discord.ui.View):
    """날씨 시스템 설정 메인 뷰"""
    def __init__(self, bot_config):
        super().__init__(timeout=300)
        self.bot_config = bot_config
        
        # 첫 번째 줄: 일반설정, 채널설정, 개별-시스템
        general_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="일반설정",
            row=0
        )
        general_button.callback = self.show_general_settings
        self.add_item(general_button)
        
        channel_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="채널설정",
            row=0
        )
        channel_button.callback = self.show_channel_settings
        self.add_item(channel_button)
        
        system_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="개별-시스템",
            row=0
        )
        system_button.callback = lambda i: self.show_channel_group_settings(i, "시스템란")
        self.add_item(system_button)
        
        # 두 번째 줄: 개별-상, 개별-중, 개별-하
        upper_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="개별-상",
            row=1
        )
        upper_button.callback = lambda i: self.show_channel_group_settings(i, "윗마을")
        self.add_item(upper_button)
        
        middle_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="개별-중",
            row=1
        )
        middle_button.callback = lambda i: self.show_channel_group_settings(i, "중간마을")
        self.add_item(middle_button)
        
        lower_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="개별-하",
            row=1
        )
        lower_button.callback = lambda i: self.show_channel_group_settings(i, "아랫마을")
        self.add_item(lower_button)
    
    async def show_general_settings(self, interaction: discord.Interaction):
        """일반 설정 모달 표시"""
        modal = WeatherBasicSettingsModal(self.bot_config)
        await interaction.response.send_modal(modal)
    
    async def show_channel_settings(self, interaction: discord.Interaction):
        """채널 설정 표시"""
        view = WeatherChannelSelectorView(interaction.guild, self.bot_config)
        await interaction.response.send_message("날씨 공지를 할 채널을 선택해 주세요!", view=view, ephemeral=True)
    
    async def show_channel_group_settings(self, interaction: discord.Interaction, group_name: str):
        """채널 그룹 설정 모달 표시"""
        modal = WeatherChannelGroupModal(group_name, self.bot_config)
        await interaction.response.send_modal(modal)

    async def interaction_check(self, interaction):
        # 관리자 권한 확인
        if str(interaction.user.id) not in self.bot_config.admin_ids:
            await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
            return False
        return True

async def handle_weather_settings(interaction, bot, bot_config):
    """날씨 설정 처리"""
    # 관리자 권한 확인
    if str(interaction.user.id) not in bot_config.admin_ids:
        await interaction.response.send_message("⛔ 권한이 없습니다.", ephemeral=True)
        return
    
    # 날씨 시스템 인스턴스 가져오기
    weather_cog = interaction.client.get_cog('WeatherCommands')
    if not weather_cog or not hasattr(weather_cog, 'weather_system'):
        await interaction.response.send_message("⚠️ 날씨 시스템 모듈이 로드되지 않았습니다.", ephemeral=True)
        return
    
    # 날씨 모듈의 GLOBAL_SETTINGS 접근
    try:
        # 모듈에서 직접 GLOBAL_SETTINGS 가져오기
        import file.weather
        global_settings = file.weather.GLOBAL_SETTINGS
        
        # 채널 그룹 로드 확인
        if hasattr(weather_cog.weather_system, 'load_channel_groups'):
            weather_cog.weather_system.load_channel_groups()
        
        # 날씨 시스템 뷰 표시
        view = WeatherSettingsView(bot_config)
        
        embed = discord.Embed(
            title="⚙️ 날씨 시스템 설정",
            description="아래 버튼을 클릭하여 날씨 시스템 설정을 관리하세요.",
            color=discord.Color.blue()
        )
        
        # 현재 설정 정보 추가
        general_settings = [
            f"날씨 시스템 활성화: {'✅' if global_settings['ENABLE_WEATHER_SYSTEM'] else '❌'}",
            f"채널별 날씨 활성화: {'✅' if global_settings['ENABLE_CHANNEL_SPECIFIC_WEATHER'] else '❌'}",
            f"공포모드 확률: {global_settings['HORROR_MODE_PROBABILITY']}%",
            f"유니크 아이템 확률: {global_settings['UNIQUE_ITEM_PROBABILITY']}%",
            f"날씨 변경 알림: {'✅' if global_settings['NOTIFY_WEATHER_CHANGES'] else '❌'}",
            f"공지 채널: #{global_settings['ANNOUNCEMENT_CHANNEL_NAME']}"
        ]
        
        embed.add_field(name="일반 설정", value="\n".join(general_settings), inline=False)
        
        # 채널 그룹 정보 추가
        channel_groups_info = []
        for group_name, channel_ids in file.weather.CHANNEL_GROUPS.items():
            channel_groups_info.append(f"{group_name}: {len(channel_ids)}개 채널/스레드")
        
        if channel_groups_info:
            embed.add_field(name="채널 그룹", value="\n".join(channel_groups_info), inline=False)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    except (ImportError, AttributeError) as e:
        log_error(f"날씨 모듈 접근 중 오류 발생: {e}", e)
        await interaction.response.send_message("⚠️ 날씨 시스템 설정에 접근할 수 없습니다.", ephemeral=True)

def setup_weather_settings(bot, bot_config):
    """날씨 설정 초기화"""
    log_debug("날씨 설정 모듈 초기화 완료")