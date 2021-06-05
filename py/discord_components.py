from typing import Type
import discord
import asyncio
import json

class InteractionEventResponseType:
  ACK_ONLY = 6
  REPLY_INTERACTION = 4
  REPLY_DEFER_INTERACTION = 5
  UPDATE_MESSAGE = 7

class InteractionGatewayEventType:
  PING = 1
  APPLICATION_COMMAND = 2
  MESSAGE_COMPONENT = 3

class MessageComponentType:
  ACITON_ROW = 1
  BUTTON = 2

class InteractionButtonParts():
  def __init__(self, **kwargs):
    self.name = kwargs.get('name')
    self.type = MessageComponentType.BUTTON
    self.emoji = kwargs.get('emoji', '')
    if self.emoji and (not isinstance(self.emoji, str)) and (not isinstance(self.emoji, discord.Emoji)):
      raise TypeError('emoji only allowed str and Emoji')
    self.label = kwargs.get('label')
    self.style = kwargs.get('style') if kwargs.get('style') else 1
    self.url = kwargs.get('url')
    self.disabled: bool = kwargs.get('disabled')
    
    if (self.style != 5) and (self.name is None):
      raise Exception('name is required')
    
    if (self.style != 5) and (self.label is None):
      raise Exception('label is required')
    
    if (self.style == 5) and (self.url is None):
      raise Exception('url is required')
    
    if self.style < 1 or self.style > 5:
      raise Exception('Invalid style number')
    
  def to_dict(self):
    
    data = {
     'type': self.type,
     'style': self.style,
     'label': self.label,
     'disabled': self.disabled
    }
    if self.emoji:
      if isinstance(self.emoji, str):
        data['emoji'] = {
          'name': self.emoji,
          'id': 0,
          'animated': False
        }
      elif isinstance(self.emoji, discord.Emoji):
        data['emoji'] = {
          'name': self.emoji.name,
          'id': self.emoji.id,
          'animated': self.emoji.animated
        }
    if self.style != 5:
      data['custom_id'] = self.name
    else:
      data['url'] = self.url
    return data

class InteractionButtonEventResponse:
  def __init__(self, **kwargs) -> None:
    self.bot = kwargs['bot']
    self.data = kwargs['data']
    self.REPLY_TOKEN = kwargs['data']['token']
    self.name = kwargs['data']['data']['custom_id']
    self.message = kwargs['message']
    self.original_message = kwargs.get('original_message')
    self.ctx = kwargs.get('ctx')
  
  async def custom_response(self, t: int, d: dict):
    route = discord.http.Route('POST', '')
    route.url = f'https://discord.com/api/v9/interactions/{self.data["id"]}/{self.REPLY_TOKEN}/callback'
    payload = {
      'type': t,
      'data': d
    }
    resp = await self.bot.http.request(route, json=payload)

  async def ack(self) -> dict:
    route = discord.http.Route('POST', '')
    route.url = f'https://discord.com/api/v9/interactions/{self.data["id"]}/{self.REPLY_TOKEN}/callback'
    payload = {
      'type': InteractionEventResponseType.ACK_ONLY
    }      
    resp = await self.bot.http.request(route, json=payload)
    return resp

  async def reply(self, text: str, **kwargs):
    route = discord.http.Route('POST', '')
    route.url = f'https://discord.com/api/v9/interactions/{self.data["id"]}/{self.REPLY_TOKEN}/callback'
    payload = {
      'type': InteractionEventResponseType.REPLY_INTERACTION,
      'data': {
        'content': text,
        'flags': 0b01000000 if kwargs.get('hidden') else False
      }
    }
    if kwargs.get('embed'):
      payload['data']['embeds'] = [kwargs.get('embed').to_dict()]
      
    resp = await self.bot.http.request(route, json=payload)

class InteractionButtonRemoteObject:
  def __init__(self, **kwargs) -> None:
    self.bot = kwargs['bot']
    self.payload = kwargs['payload']
    self.id = int(kwargs['payload']['id'])
    self.channel_id = int(kwargs['payload']['channel_id'])
    try:
      self.message = self.bot._get_state().create_message(channel=self.bot.get_channel(self.channel_id), data=self.payload)
    except:
      self.message = None
    self.original_message = kwargs.get('orignal_message')
    self.guild_id = None
    self.timeout = kwargs.get('timeout', None)
    self._callback = None
  
  def _update_message_object(self, p):
    try:
      self.message = self.bot._get_state().create_message(channel=self.bot.get_channel(self.channel_id), data=p)
    except:
      self.message = None

  async def delete(self):
    route = discord.http.Route('DELETE', f'/channels/{self.channel_id}/messages/{self.id}')
    resp = await self.bot.http.request(route)
    self.message = None
  
  async def edit(self, nd):
    await self.update(nd)
  
  async def update(self, nd):
    route = discord.http.Route('PATCH', f'/channels/{self.channel_id}/messages/{self.id}')
    payload = nd.json
    resp = await self.bot.http.request(route, json=payload)
    self.payload = resp
    self._update_message_object(resp)
    
  def set_callback(self, func):
    if not asyncio.iscoroutinefunction(func):
      raise TypeError('func must be awaitable function')
    self._callback = func
  
  async def _event_handler_process(self, **kwargs):
    while True:
      d = await self.wait_for_press(timeout=kwargs.get('timeout'))
      ctx = None
      try:
        ctx = await self.bot.get_context(self.message)
      except:
        pass
      await self._callback(ctx, d)
      if kwargs.get('timeout') is not None:
        break
  
  def start_receive(self, **kwargs):
    if not self._callback:
      raise Exception('please set callback function before start receiving events')
    self._callback_task = asyncio.create_task(self._event_handler_process(timeout=kwargs.get('timeout')))
    return self._callback_task
    
  def stop_receive(self):
    if self._callback_task:
      try:
        self._callback_task.cancel()
      except:
        pass
      self._callback_task = None
  
  def clear_callback(self):
    if self._callback_task:
      if (not self._callback_task.done()) and (not self._callback_task.cancelled()):
        self._callback_task.cancel()
    self._callback = None
    self._callback_task = None
  
  async def wait_for_press(self, **kwargs):
    data = await self.bot.wait_for('socket_response', check=lambda d: d['t'] == 'INTERACTION_CREATE' and d['d']['message']['id'] == str(self.id), timeout=kwargs.get('timeout'))
    ctx = None
    try:
      ctx = await self.bot.get_context(self.message)
    except:
      pass
    return InteractionButtonEventResponse(bot=self.bot, message=self.message, original_message=self.original_message, ctx=ctx, data=data['d'])

class InteractionButton():
  def __init__(self, **kwargs):
    self.bot = kwargs.get('bot')
    if (not isinstance(self.bot, discord.Client)) and (not isinstance(self.bot, discord.ext.commands.Bot)) and (not isinstance(self.bot, discord.AutoShardedClient)) and (not isinstance(self.bot, discord.ext.commands.AutoShardedBot)):
      raise TypeError('bot must be Client or Bot')
    self.original_message = kwargs.get('original_message')
    self.embed = kwargs.get('embed')
    if self.embed and (not isinstance(self.embed, discord.Embed)):
      raise TypeError('embed must be Embed')
    self.json = {}
    self.buttons = []
  
  def add_button(self, btn: InteractionButtonParts):
    self.json = {}
    if len(self.buttons)==5:
      raise Exception('buttons can be added up to 5 items') 
    
    self.buttons.append(btn)
  
  def add_buttons(self, btns):
    self.json = {}
    if len(self.buttons) + len(btns) > 5:
      raise Exception('buttons can be added up to 5 items')
    
    self.buttons.extend(btns)
  
  def remove_button(self, btn: InteractionButtonParts):
    self.json = {}
    self.buttons.remove(btn)
  
  def get_button(self, index: int):
    return self.buttons[index]
  
  def build(self, **kwargs):
    data = {}
    if kwargs.get('content'):
      data['content'] = kwargs.get('content')
    if kwargs.get('embed'):
      self.embed = kwargs.get('embed').to_dict()
      data['embed'] = kwargs.get('embed').to_dict()
    data['components'] = [{
      'type': MessageComponentType.ACITON_ROW,
      'components': []
    }]
    for parts in self.buttons:
      data['components'][0]['components'].append(parts.to_dict())
    self.json = data
  
  async def send(self, **kwargs):
    if not kwargs.get('channel'):
      raise Exception('kwargs channel required')
    if not isinstance(kwargs.get('channel'), discord.TextChannel):
      raise Exception('channel must be TextChannel')
    if not self.json:
      raise Exception('Execute build() first')
    channel = kwargs.get('channel')
    route = discord.http.Route('POST', f'/channels/{channel.id}/messages', channel_id=channel.id)
    resp = await self.bot.http.request(route, json=self.json)
    return InteractionButtonRemoteObject(bot=self.bot, payload=resp)
  

class InteractionButtonStylesBase():
  def __init__(self):
    pass
    
  def primary(self):
    return 1
  
  def secondary(self):
    return 2
  
  def success(self):
    return 3
  
  def danger(self):
    return 4
  
  def link(self):
    return 5
    
  def blurple(self):
    return self.primary()
  
  def grey(self):
    return self.secondary()
  
  def green(self):
    return self.success()
  
  def red(self):
    return self.danger()
  
  def url(self):
    return self.link()
    
InteractionButtonStyles = InteractionButtonStylesBase()
