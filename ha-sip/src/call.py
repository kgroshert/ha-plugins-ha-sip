import os

import ha
import sip_types

import pjsua2 as pj


class Call(pj.Call):
    def __init__(self, end_point: pj.Endpoint, account: pj.Account, call_id: str, uri_to_call: str, menu: sip_types.Menu, callback: sip_types.CallCallback):
        pj.Call.__init__(self, account, call_id)
        self.end_point = end_point
        self.account = account
        self.uri_to_call = uri_to_call
        self.menu = menu
        self.callback = callback
        self.connected: bool = False
        self.callback(sip_types.CallStateChange.CALL, self.uri_to_call, self)
        self.player = None
        self.audio_media = None

    def onCallState(self, prm):
        ci = self.getInfo()
        if ci.state == pj.PJSIP_INV_STATE_CONFIRMED:
            self.connected = True
            print('| Call connected')
        elif ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            self.connected = False
            self.account.c = None
            self.account.acceptCall = False
            self.account.inCall = False
            self.account.call_id = None
            self.callback(sip_types.CallStateChange.HANGUP, self.uri_to_call, self)
            print('| Call disconnected')

    def onCallMediaState(self, prm):
        call_info = self.getInfo()
        print('| onCallMediaState', call_info.state)
        for media_index, media in enumerate(call_info.media):
            if media.type == pj.PJMEDIA_TYPE_AUDIO and call_info.stateText == 'CONFIRMED':
                self.audio_media = self.getAudioMedia(media_index)
                self.handle_menu_entry(self.menu)

    def onDtmfDigit(self, prm: pj.OnDtmfDigitParam):
        print('| onDtmfDigit: digit', prm.digit)
        digit = prm.digit
        if not self.menu:
            return
        choices = self.menu.get('choices')
        if choices and digit in choices:
            self.menu = choices[digit]
        self.handle_menu_entry(self.menu)

    def handle_menu_entry(self, menu_entry: sip_types.Menu) -> None:
        if not menu_entry:
            return
        message = menu_entry.get('message', 'No message provided')
        self.play_message(message)
        action = menu_entry.get('action')
        if not action:
            print('| No action supplied')
            return
        domain = action.get('domain')
        service = action.get('service')
        entity_id = action.get('entity_id')
        if (not domain) or (not service) or (not entity_id):
            print('| Error: one of domain, service or entity_id was not provided')
            return
        print('| Calling home assistant service on domain', domain, 'service', service, 'with entity', entity_id)
        ha.call_service(domain, service, entity_id)

    def play_message(self, message: str) -> None:
        print('| Playing message:', message)
        self.player = pj.AudioMediaPlayer()
        sound_file_name, must_be_deleted = ha.create_and_get_tts(message)
        self.player.createPlayer(file_name=sound_file_name, options=pj.PJMEDIA_FILE_NO_LOOP)
        self.player.startTransmit(self.audio_media)
        if must_be_deleted:
            # looks like `createPlayer` is loading the file to memory, and it can be removed already
            os.remove(sound_file_name)

    def hangup_call(self):
        call_prm = pj.CallOpParam(True)
        pj.Call.hangup(self, call_prm)


def make_call(ep: pj.Endpoint, account: pj.Account, uri_to_call: str, menu: sip_types.Menu, callback: sip_types.CallCallback):
    new_call = Call(ep, account, pj.PJSUA_INVALID_ID, uri_to_call, menu, callback)
    call_param = pj.CallOpParam(True)
    new_call.makeCall(uri_to_call, call_param)
    return new_call
