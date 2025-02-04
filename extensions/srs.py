import os
import shutil
import subprocess
import win32api
from configparser import RawConfigParser
from core import Extension, DCSServerBot, utils, report, Server
from typing import Optional


class SRS(Extension):
    def __init__(self, bot: DCSServerBot, server: Server, config: dict):
        self.cfg = RawConfigParser()
        self.cfg.optionxform = str
        super().__init__(bot, server, config)
        self.process = None

    def load_config(self) -> Optional[dict]:
        self.cfg.read(os.path.expandvars(self.config['config']), encoding='utf-8')
        return {s: dict(self.cfg.items(s)) for s in self.cfg.sections()}

    async def prepare(self) -> bool:
        # Set SRS port if necessary
        dirty = False
        if 'port' in self.config and int(self.cfg['Server Settings']['SERVER_PORT']) != int(self.config['port']):
            self.cfg.set('Server Settings', 'SERVER_PORT', str(self.config['port']))
            self.log.info(f"  => {self.server.name}: SERVER_PORT set to {self.config['port']}")
            dirty = True
        if 'awacs' in self.config and self.cfg['General Settings']['EXTERNAL_AWACS_MODE'] != str(self.config['awacs']).lower():
            self.cfg.set('General Settings', 'EXTERNAL_AWACS_MODE', str(self.config['awacs']).lower())
            self.log.info(f"  => {self.server.name}: EXTERNAL_AWACS_MODE set to {self.config['awacs']}")
            dirty = True
        if 'blue_password' in self.config and self.cfg['External AWACS Mode Settings']['EXTERNAL_AWACS_MODE_BLUE_PASSWORD'] != self.config['blue_password']:
            self.cfg.set('External AWACS Mode Settings', 'EXTERNAL_AWACS_MODE_BLUE_PASSWORD', self.config['blue_password'])
            self.log.info(f"  => {self.server.name}: EXTERNAL_AWACS_MODE_BLUE_PASSWORD set to {self.config['blue_password']}")
            dirty = True
        if 'red_password' in self.config and self.cfg['External AWACS Mode Settings']['EXTERNAL_AWACS_MODE_RED_PASSWORD'] != self.config['red_password']:
            self.cfg.set('External AWACS Mode Settings', 'EXTERNAL_AWACS_MODE_RED_PASSWORD', self.config['red_password'])
            self.log.info(f"  => {self.server.name}: EXTERNAL_AWACS_MODE_RED_PASSWORD set to {self.config['red_password']}")
            dirty = True
        if dirty:
            path = os.path.expandvars(self.config['config'])
            with open(path, 'w') as ini:
                self.cfg.write(ini)
            self.locals = self.load_config()
        # Change DCS-SRS-AutoConnectGameGUI.lua if necessary
        autoconnect = os.path.expandvars(f"%USERPROFILE%\\Saved Games\\{self.server.installation}\\Scripts\\Hooks\\DCS-SRS-AutoConnectGameGUI.lua")
        host = self.config['host'] if 'host' in self.config else self.bot.external_ip
        port = self.config['port'] if 'port' in self.config else self.locals['Server Settings']['SERVER_PORT']
        if os.path.exists(autoconnect):
            shutil.copy2(autoconnect, autoconnect + '.bak')
            with open('extensions\\lua\\DCS-SRS-AutoConnectGameGUI.lua') as infile:
                with open(autoconnect, 'w') as outfile:
                    for line in infile.readlines():
                        if line.startswith('SRSAuto.SERVER_SRS_HOST_AUTO = '):
                            line = "SRSAuto.SERVER_SRS_HOST_AUTO = false -- if set to true SRS will set the " \
                                   "SERVER_SRS_HOST for you! - Currently disabled\n"
                        elif line.startswith('SRSAuto.SERVER_SRS_PORT = '):
                            line = f'SRSAuto.SERVER_SRS_PORT = "{port}" --  SRS Server default is 5002 TCP & UDP\n'
                        elif line.startswith('SRSAuto.SERVER_SRS_HOST = '):
                            line = f'SRSAuto.SERVER_SRS_HOST = "{host}" -- overridden if SRS_HOST_AUTO is true -- set to your PUBLIC ipv4 address\n'
                        outfile.write(line)
        else:
            self.log.info('- SRS autoconnect is not enabled for this server.')
        return True

    async def startup(self) -> bool:
        if 'autostart' not in self.config or self.config['autostart']:
            self.log.debug(r'Launching SRS server with: "{}\SR-Server.exe" -cfg="{}"'.format(
                os.path.expandvars(self.config['installation']), os.path.expandvars(self.config['config'])))
            self.process = subprocess.Popen(['SR-Server.exe', '-cfg={}'.format(
                os.path.expandvars(self.config['config']))],
                                            executable=os.path.expandvars(self.config['installation']) + r'\SR-Server.exe')
        return self.is_running()

    async def shutdown(self):
        if 'autostart' not in self.config or self.config['autostart']:
            p = self.process or utils.find_process('SR-Server.exe', self.server.installation)
            if p:
                p.kill()
                self.process = None
                return True
            else:
                return False
        else:
            return True

    def is_running(self) -> bool:
        if self.process:
            if self.process.poll():
                self.process = None
                return False
            else:
                return True
        server_ip = self.locals['Server Settings']['SERVER_IP'] if 'SERVER_IP' in self.locals['Server Settings'] else '127.0.0.1'
        if server_ip == '0.0.0.0':
            server_ip = '127.0.0.1'
        return utils.is_open(server_ip, self.locals['Server Settings']['SERVER_PORT'])

    @property
    def version(self) -> str:
        info = win32api.GetFileVersionInfo(
            os.path.expandvars(self.config['installation']) + r'\SR-Server.exe', '\\')
        version = "%d.%d.%d.%d" % (info['FileVersionMS'] / 65536,
                                   info['FileVersionMS'] % 65536,
                                   info['FileVersionLS'] / 65536,
                                   info['FileVersionLS'] % 65536)
        return version

    def render(self, embed: report.EmbedElement, param: Optional[dict] = None):
        if self.locals:
            host = self.config['host'] if 'host' in self.config else self.bot.external_ip
            value = f"{host}:{self.locals['Server Settings']['SERVER_PORT']}"
            show_passwords = self.config['show_passwords'] if 'show_passwords' in self.config else True
            if show_passwords and self.locals['General Settings']['EXTERNAL_AWACS_MODE'] == 'true' and \
                    'External AWACS Mode Settings' in self.locals:
                blue = self.locals['External AWACS Mode Settings']['EXTERNAL_AWACS_MODE_BLUE_PASSWORD']
                red = self.locals['External AWACS Mode Settings']['EXTERNAL_AWACS_MODE_RED_PASSWORD']
                if blue or red:
                    value += f'\n🔹 Pass: {blue}\n🔸 Pass: {red}'
            embed.add_field(name="SRS (online)" if self.is_running() else "SRS (offline)", value=value)

    def verify(self) -> bool:
        # check if SRS is installed
        if 'installation' not in self.config or \
                not os.path.exists(os.path.expandvars(self.config['installation']) + r'\SR-Server.exe'):
            self.log.debug("SRS executable not found in {}".format(self.config['installation'] + r'\SR-Server.exe'))
            return False
        # do we have a proper config file?
        if 'config' not in self.config or not os.path.exists(os.path.expandvars(self.config['config'])):
            self.log.debug(f"SRS config not found in {self.config['config']}")
            return False
        if self.server.installation not in self.config['config']:
            self.log.warning(f"- Please move your SRS configuration from {self.config['config']} to "
                             f"Saved Games\\{self.server.installation}\\Config\\SRS.cfg")
        return True
