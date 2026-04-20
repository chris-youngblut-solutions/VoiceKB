import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import St from 'gi://St';

import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {QuickToggle, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

const SERVICE = 'voicekb.service';
const STATE = {STOPPED: 'stopped', WARMING: 'warming', READY: 'ready', ERROR: 'error'};
const SUBTITLE = {
    [STATE.STOPPED]: _('Off'),
    [STATE.WARMING]: _('Warming…'),
    [STATE.READY]: _('Ready'),
    [STATE.ERROR]: _('Error'),
};

function _ (s) { return s; }

const VoiceKBToggle = GObject.registerClass(
class VoiceKBToggle extends QuickToggle {
    _init(extensionPath, settings) {
        super._init({
            title: _('VoiceKB'),
            toggleMode: true,
            gicon: Gio.icon_new_for_string(`${extensionPath}/icons/voicekb-symbolic.svg`),
        });
        this.add_style_class_name('voicekb-toggle');
        this._settings = settings;
        this._pending = null;

        this._settings.connect('changed::service-state', () => this._refreshSubtitle());
        this._refreshSubtitle();
        this.connect('clicked', () => this._onClicked());

        this._syncFromSystemd();
    }

    _refreshSubtitle() {
        const s = this._settings.get_string('service-state');
        this.subtitle = SUBTITLE[s] ?? s;
    }

    _setState(state) {
        this._settings.set_string('service-state', state);
    }

    _spawn(argv, cb) {
        try {
            const proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE);
            this._pending = proc;
            proc.wait_async(null, (_src, res) => {
                this._pending = null;
                try {
                    proc.wait_finish(res);
                    cb(proc.get_successful(), proc.get_exit_status());
                } catch (e) {
                    cb(false, -1);
                }
            });
        } catch (e) {
            cb(false, -1);
        }
    }

    _onClicked() {
        if (this.checked) {
            this._setState(STATE.WARMING);
            this._spawn(['systemctl', '--user', 'start', SERVICE], (ok) => {
                this._setState(ok ? STATE.READY : STATE.ERROR);
                if (!ok) this.checked = false;
            });
        } else {
            this._spawn(['systemctl', '--user', 'stop', SERVICE], (ok) => {
                this._setState(ok ? STATE.STOPPED : STATE.ERROR);
            });
        }
    }

    _syncFromSystemd() {
        this._spawn(['systemctl', '--user', 'is-active', SERVICE], (ok) => {
            this.checked = ok;
            this._setState(ok ? STATE.READY : STATE.STOPPED);
        });
    }

    destroy() {
        if (this._pending) {
            try { this._pending.force_exit(); } catch (e) {}
            this._pending = null;
        }
        super.destroy();
    }
});

const VoiceKBIndicator = GObject.registerClass(
class VoiceKBIndicator extends SystemIndicator {
    _init(extensionPath, settings) {
        super._init();
        this._toggle = new VoiceKBToggle(extensionPath, settings);
        this.quickSettingsItems.push(this._toggle);
    }

    destroy() {
        this.quickSettingsItems.forEach(i => i.destroy());
        this.quickSettingsItems = [];
        super.destroy();
    }
});

export default class VoiceKBExtension extends Extension {
    enable() {
        this._settings = this.getSettings();
        this._indicator = new VoiceKBIndicator(this.path, this._settings);
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
    }

    disable() {
        this._indicator?.destroy();
        this._indicator = null;
        this._settings = null;
    }
}
