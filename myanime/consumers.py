import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class WatchPartyConsumer(AsyncWebsocketConsumer):
    # Статическая переменная для хранения данных комнат в памяти
    rooms_data = {}

    async def connect(self):
        # 1. Сначала принимаем соединение (фикс для Daphne/Django 6.0)
        await self.accept()

        # 2. Инициализируем базовые параметры
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'party_{self.room_name}'
        self.user = self.scope['user']

        # 3. Создаем структуру комнаты, если её нет
        if self.room_group_name not in self.rooms_data:
            self.rooms_data[self.room_group_name] = {
                'members': [],
                'auto_skip': False
            }

        # 4. Получаем аватарку асинхронно
        user_avatar = await self.get_user_avatar(self.user)

        # 5. Собираем данные о пользователе
        user_info = {
            'username': self.user.username if self.user.is_authenticated else "Аноним",
            'channel_name': self.channel_name,
            'avatar_url': user_avatar
        }

        # 6. Добавляем пользователя в список участников (ТОЛЬКО ОДИН РАЗ)
        self.rooms_data[self.room_group_name]['members'].append(user_info)

        # 7. Добавляем канал в группу Channel Layer
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        # 8. Отправляем текущие настройки комнаты новичку
        current_settings = self.rooms_data[self.room_group_name]['auto_skip']
        await self.send(text_data=json.dumps({
            'action': 'apply_room_settings',
            'autoSkip': current_settings
        }))

        # 9. Уведомляем всех об обновлении списка участников
        await self.broadcast_members()

        # 10. Запрашиваем синхронизацию времени у тех, кто уже в комнате
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'request_sync',
                'requester': self.channel_name
            }
        )

    @database_sync_to_async
    def get_user_avatar(self, user):
        if not user.is_authenticated:
            return "/static/img/default-avatar.png"
        try:
            if hasattr(user, 'profile') and user.profile.avatar:
                return user.profile.avatar.url
        except Exception:
            pass
        return "/static/img/default-avatar.png"

    async def disconnect(self, close_code):
        if self.room_group_name in self.rooms_data:
            # Удаляем участника по его channel_name
            self.rooms_data[self.room_group_name]['members'] = [
                u for u in self.rooms_data[self.room_group_name]['members']
                if u['channel_name'] != self.channel_name
            ]

            # Если в комнате пусто — удаляем данные комнаты
            if not self.rooms_data[self.room_group_name]['members']:
                del self.rooms_data[self.room_group_name]

        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        await self.broadcast_members()

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'update_room_settings':
            if self.room_group_name in self.rooms_data:
                self.rooms_data[self.room_group_name]['auto_skip'] = data.get('autoSkip')
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'settings_update',
                        'autoSkip': data.get('autoSkip')
                    }
                )
            return

        if action == 'sync_response':
            await self.channel_layer.send(data['target'], {
                'type': 'video_event',
                'action': 'seek',
                'time': data['time'],
                'episode_id': data.get('episode_id'),
                'sender': self.channel_name
            })
            return

        # События плеера
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'video_event',
                'action': action,
                'time': data.get('time'),
                'episode_id': data.get('episode_id'),
                'ordinal': data.get('ordinal'),
                'user': data.get('user'), # Передаем имя для буферизации
                'sender': self.channel_name
            }
        )

    # --- Хендлеры сообщений группы ---

    async def video_event(self, event):
        if self.channel_name != event.get('sender'):
            await self.send(text_data=json.dumps({
                'action': event['action'],
                'time': event.get('time'),
                'episode_id': event.get('episode_id'),
                'ordinal': event.get('ordinal'),
                'user': event.get('user')
            }))

    async def request_sync(self, event):
        if self.channel_name != event['requester']:
            await self.send(text_data=json.dumps({
                'action': 'ask_for_sync',
                'target': event['requester']
            }))

    async def settings_update(self, event):
        await self.send(text_data=json.dumps({
            'action': 'apply_room_settings',
            'autoSkip': event['autoSkip']
        }))

    async def broadcast_members(self):
        if self.room_group_name not in self.rooms_data:
            return

        members_list = self.rooms_data[self.room_group_name]['members']
        members = []
        for i, u in enumerate(members_list):
            members.append({
                'username': u['username'],
                'avatar': u['avatar_url'],
                'is_host': i == 0 # Первый в списке — всегда хост
            })

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'members_update',
                'members': members
            }
        )

    async def members_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'members_update',
            'members': event['members']
        }))
