
import logging
import json

class RuntimeConfig:

    def __init__(self, json_file):
        self.load_option(json_file)
    
    def load_option(self, json_file):
        try:
            _settings_file = open(json_file)
            self.env = json.load(_settings_file)
        except Exception as e:
            logging.error(e)

    def get(self, group, key, default_value=None):
        try:
            return self.env[group][key] 
        except Exception as e:
            logging.error(e)
            return default_value

