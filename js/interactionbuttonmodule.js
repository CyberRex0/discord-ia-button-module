const Discord = require('discord.js');
const fetch = require('node-fetch');

class InteractionButton {
    constructor (bot) {
        this.bot = bot;
        this.json = {};
        this.buttons = [];
        if (!this.bot instanceof Discord.Client) throw 'bot must be Client';
    }

    add_button (btn) {
        if (btn instanceof InteractionButtonParts == false) {
            throw 'btn must be InteractionButtonParts';
        }
        this.buttons.push(btn);
        this.json = {};
    }

    add_buttons (btns) {
        btns.forEach((v, i) => {
            if (v instanceof InteractionButtonParts == false) {
                throw 'btn must be InteractionButtonParts';
            }
        });
        this.buttons = this.buttons.concat(btns);
        this.json = {};
    }

    remove_button (btn) {
        if (btn instanceof InteractionButtonParts == false) {
            throw 'btn must be InteractionButtonParts';
        }
        this.buttons.forEach((v, i) => {
            if (v == btn) {
                var index = this.buttons.indexOf(v);
                if (index == -1) return;
                this.buttons.splice(index, 1);
            }
        });
        this.json = {};
    }

    get_button (index) {
        return this.buttons[index];
    }

    build () {
        var data = {components: [
            {type: MessageComponentType.ACTION_ROW, components: []}
        ]};
        this.buttons.forEach((v, i) => {
            data.components[0].components.push(v.to_dict());
        });
        this.json = data;
    }

    async send (params, f) {
        if (!this.json) throw 'please call build() before send';
        if (params.content) this.json.content = params.content;
        if (params.embed) {
            if (!params.embed instanceof Discord.MessageEmbed) throw 'embed must be MessageEmbed';
            this.json.embed = params.embed.toJSON();
        }
        if (!this.json.content && !this.json.embed) this.json.content = '.';
        if (!params.channel) throw 'please specify the location of channel to send';
        if (!params.channel instanceof Discord.TextChannel) throw 'channel must be TextChannel';
        var url = `https://discord.com/api/v8/channels/${params.channel.id}/messages`;
        var request = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bot '+ this.bot.token
            },
            redirect: 'follow',
            body: JSON.stringify(this.json)
        });
        if (!request.ok) {
            request.text().then((e) => {
                throw 'Discord API was returned an error:\n'+ e;
            });
        }
        params.bot = this.bot;
        if (!f) return;
        request.json().then((j) => {
            f(new InteractionButtonRemoteObject({bot: params.bot, channel: params.channel, data: j}));
        });
    }
 }

 class InteractionButtonEventResponse {
     constructor (params) {
         this.data = params.data;
         this.bot = params.bot;
         this.REPLY_TOKEN = params.data.token;
         this.name = params.data.data.custom_id;
         this.channel_id = params.data.channel_id;
         this.guild_id = params.data.guild_id;
         this.user = params.data.member;
         this.message = params.message;
         this.channel = params.channel;
     }

     async custom_response (t, d) {
        var url = `https://discord.com/api/v9/interactions/${this.data.id}/${this.REPLY_TOKEN}/callback`;
        var payload = {
            'type': t,
            'data': d
        };
        var request = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bot '+ this.bot.token
            },
            redirect: 'follow',
            body: JSON.stringify(payload)
        });
        if (!request.ok) {
            request.text().then((e) => {
                throw 'Discord API was returned an error:\n'+ e;
            });
        }
     }

     async ack () {
        var url = `https://discord.com/api/v9/interactions/${this.data.id}/${this.REPLY_TOKEN}/callback`;
        var payload = {
            'type': InteractionEventResponseType.ACK_ONLY,
            'data': null
        };
        var request = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bot '+ this.bot.token
            },
            redirect: 'follow',
            body: JSON.stringify(payload)
        });
        if (!request.ok) {
            request.text().then((e) => {
                throw 'Discord API was returned an error:\n'+ e;
            });
        }
     }

     async reply (text, params = {}) {
        var url = `https://discord.com/api/v9/interactions/${this.data.id}/${this.REPLY_TOKEN}/callback`;
        var payload = {
            'type': InteractionEventResponseType.REPLY_INTERACTION,
            'data': {
                'content': text,
                'flags': params.hidden ? 0b01000000 : 0
            }
        };
        var request = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bot '+ this.bot.token
            },
            redirect: 'follow',
            body: JSON.stringify(payload)
        });
        if (!request.ok) {
            request.text().then((e) => {
                throw 'Discord API was returned an error:\n'+ e;
            });
        }
     }
 }

 class InteractionButtonRemoteObject {
     constructor (params) {
        if(!params.data) throw 'InternalError: NO_DATA';
        this.payload = params.data;
        this.id = params.data.id;
        this.bot = params.bot;
        this._callback = null;
        this._event_handler_process = async (data) => {
            if (data.t == 'INTERACTION_CREATE') {
                if (data.d.type == InteractionGatewayEventType.MESSAGE_COMPONENT) {
                    if (data.d.message.id == this.id) {
                        const ctx = new InteractionButtonEventResponse({bot: this.bot, channel: this.channel, message: this.message, data: data.d});
                        await this._callback(ctx);
                    }
                }
            }
        };
        this.channel = params.channel;
        this.message = new Discord.Message(this.bot, this.payload, this.channel);
     }

     set_callback (func) {
         if (typeof func != 'function') throw 'func must be function';
         this._callback = func;
     }

     clear_callback () {
         this.bot.off('raw', this._event_handler_process);
         this._callback = null;
     }

     start_receive () {
         if (!this._callback) throw 'please set callback before start receiving events';
         this.bot.on('raw', this._event_handler_process);
     }

     stop_receive () {
         this.bot.off('raw', this._event_handler_process);
     }
 }

 class InteractionButtonParts {
    constructor (params) {
        this.name = params.name;
        this.label = params.label;
        this.style = params.style ? params.style : 1;
        this.url = params.url;
        this.emoji = params.emoji;
        this.disabled = (params.disabled!=undefined&&params.disabled!=null) ? params.disabled : false;
        if (!this.name && !this.url) throw 'name is required';
        if (!this.label) throw 'label is required';
        if (this.style < 1 || this.style > 5) throw 'invalid style number';
        if (this.style === 5 && !this.url) throw 'url is required';
        if (this.emoji) {
            if (!this.emoji instanceof Discord.GuildEmoji && typeof this.emoji != 'string') throw 'emoji must be string or GuildEmoji';
        }
    }

    to_dict () {
        var data = {
            type: MessageComponentType.BUTTON,
            style: this.style,
            label: this.label,
            disabled: this.disabled
        };
        if (this.style === 5) {
            data.url = this.url;
        }else{
            data.custom_id = this.name;
        }
        if (this.emoji) {
            if (typeof this.emoji == 'string') {
                data.emoji = {
                    id: 0,
                    name: this.emoji,
                    animated: false
                };
            }
            if (this.emoji instanceof Discord.GuildEmoji) {
                data.emoji = {
                    id: this.emoji.id,
                    name: this.emoji.name,
                    animated: this.emoji.animated
                };
            }
        }
        return data;
    }
 }

 class InteractionEventResponseType {
     constructor () {

     }
     static ACK_ONLY = 6;
     static REPLY_INTERACTION = 4;
     static REPLY_DEFER_INTERACTION = 5;
     static UPDATE_MESSAGE = 7;
 }

 class InteractionGatewayEventType {
     constructor () {

     }
     static PING = 1;
     static APPLICATION_COMMAND = 2;
     static MESSAGE_COMPONENT = 3;
 }
 
 class MessageComponentType {
     constructor () {

     }
     static ACTION_ROW = 1;
     static BUTTON = 2;
 }

 module.exports = {InteractionButton, InteractionButtonParts, InteractionEventResponseType};