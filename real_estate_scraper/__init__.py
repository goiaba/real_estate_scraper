import os
import json
from logging.config import fileConfig

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def path_from_root_project_dir(filename):
    return os.path.join(ROOT_DIR, filename)


def load_config():
    config_file = path_from_root_project_dir("config.json")
    with open(config_file, 'r') as file:
        return json.load(file)


def get_config(key, default=None):
    def rec(curr, keys):
        if not keys:
            return curr
        if keys[0] not in curr:
            if default:
                return default
            raise Exception("\'%s\' nao pertence a estrutura \'%s\'." %
                            (keys[0], curr))
        return rec(curr[keys[0]], keys[1:])

    if not key:
        raise Exception("Nenhuma chave de configuracao passada.")
    if key[0] == ':' or key[-1:] == ":":
        raise Exception("Chave invalida: %s" % key)
    return rec(cfg, key.split(":"))


cfg = load_config()
log_file_path = get_config('conf:logging:config_file_path')
log_config_file = path_from_root_project_dir(log_file_path)
fileConfig(log_config_file)
