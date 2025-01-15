# consumers.py

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class ThemeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        pass

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        pass

    async def update_theme(self, event):
        pass
