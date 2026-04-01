"""Audio mixer stub (no-op).

Accepts all sound/music calls without doing anything.
Will be replaced with a real implementation later.
"""


class MixerStub:

    def play_sound(self, res_id, freq, vol, channel):
        pass

    def play_music(self, res_num, delay, pos):
        pass

    def stop_all(self):
        pass
