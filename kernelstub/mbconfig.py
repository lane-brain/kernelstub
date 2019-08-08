#!/usr/bin/python3

"""
 kernelstub
 Comprehensive automatic ESP Management for Linux.

 Copyright 2017-2018 Ian Santopietro <isantop@gmail.com>

Permission to use, copy, modify, and/or distribute this software for any purpose
with or without fee is hereby granted, provided that the above copyright notice
and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS
OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER
TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF
THIS SOFTWARE.

Please see the provided LICENSE.txt file for additional distribution/copyright
terms.

Code to load multiboot-compatible configuration
"""

import json
import logging
import os

from . import mbdrive as drive

CURRENT_CONFIGURATION_REVISION = 4

class ConfigError(Exception):
    """Exception used for configuration errors. Pass details of the error in msg.

    Arguments: 
        msg (str): Human-readable message describing the error that threw the 
            exception.
        code (:obj:`int`, optional, default=5): Exception error code.
    """
    def __init__(self, msg, code=5):
        self.msg = msg
        self.code = code

class SystemConfiguration:
    """ An object representing the system configuration.

    Arguments:
        config_path (str): The path to the system kernelstub configuration.
            Default is `/etc/kernelstub/system`
    
    Attributes:
        config_path (str): The path to the system kernelstub configuration.

    """

    def __init__(self, config_path='/etc/kernelstub'):
        self.log = logging.getLogger('kernelstub.SystemConfiguration')
        self.log.debug('Loaded kernelstub.SystemConfiguration')
        self.config = {}
        self.config_path = config_path
        self.update_config()
        self.config_rev = CURRENT_CONFIGURATION_REVISION
        self.esp = drive.Drive(mount_point=self.esp_path)
    
    @property
    def config_rev(self):
        """ int: The revision of the current configuration. """
        return self.config['config_rev']
    
    @config_rev.setter
    def config_rev(self, revision):
        self.config['config_rev'] = revision

    @property
    def config_path(self):
        """ str: The path to the system configuration file."""
        return self._config_path
    
    @config_path.setter
    def config_path(self, config_path):
        """ When we set this path, load it and update configuration internally.
        """
        self.log.debug('Setting configuration path, %s', config_path)
        if config_path:
            self._config_path = config_path
            self.load_config()

    @property
    def esp_path(self):
        """ str: The path to the ESP mountpoint on the system."""
        return self.config['esp_path']
    
    @esp_path.setter
    def esp_path(self, esp_path):
        if esp_path:
            self.config['esp_path'] = esp_path
            self.save_config()
    
    @property
    def default_entry(self):
        """ str: the entry_id of the default entry. """
        return self.config['default_entry']

    @default_entry.setter
    def default_entry(self, entry_id):
        if entry_id:
            self.config['default_entry'] = entry_id
            self.save_config()
    
    @property
    def menu_timeout(self):
        """int: The number of seconds for which to display the boot menu. 
        After this, the default_entry is loaded.
        """
        return self.config['menu_timeout']
    
    @menu_timeout.setter
    def menu_timeout(self, timeout):
        self.config['menu_timeout'] = int(timeout)
        self.save_config()
    
    def update_config(self):
        """ Update the configuration to a new version if necessary."""
        # The configuration is current
        self.log.debug('Checking if configuration is current...')
        if self.config_rev == CURRENT_CONFIGURATION_REVISION:
            self.log.debug('Configuration revision %s is current', self.config_rev)
            return
        else:
            raise ConfigError(
                'Invalid configuration detected, '
                f'config_rev {self.config_rev} is not understood.'
            )
    
    def load_config(self):
        """ Load a configuration file from disk."""
        config_dir = os.path.dirname(self.config_path)
        self.log.debug('Loading configuration from %s', self.config_path)

        if not os.path.exists(config_dir):
            self.log.warn('No configuration directory %s, creating it', config_dir)
            os.makedirs(config_dir)

        try: 
            with open(self.config_path) as config_file:
                self.config = json.load(config_file)
        except FileNotFoundError:
            self.log.warn(
                'No configuration found in %s, setting defaults.',
                self.config_path
            )
            self.esp_path = '/boot/efi'
            self.menu_timeout = 0
            self.config_rev = CURRENT_CONFIGURATION_REVISION

        self.log.debug('Sucessfully loaded config from %s', self.config_path)
        
    
    def save_config(self):
        """ Save our current configuration to disk."""
        with open(self.config_path, mode='w') as config_file:
            json.dump(self.config, config_file, indent=2)
        self.save_loader_conf()
        self.log.debug(
            'Saved configuration to %s and written to ESP', 
            self.config_path
        )
    
    def save_loader_conf(self):
        """ Save the configuration to the loader configuration."""
        loader_conf_path = os.path.join(self.esp_path, 'loader/loader.conf')

        loader_conf = []
        loader_conf.append("## THIS FILE IS AUTOMATICALLY GENERATED!\n")
        loader_conf.append("## To modify this file, use `kernelstub`\n\n")
        loader_conf.append(f'default {self.default_entry}\n')
        loader_conf.append(f'timeout {str(self.menu_timeout)}\n')

        with open(loader_conf_path, mode='w') as loader_conf_file:
            loader_conf_file.writelines(loader_conf)
