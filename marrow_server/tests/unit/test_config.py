import importlib
import os

import config


def test_ExternalDebug_NoEnvVarSet_DefaultsFalse():
    env_backup = os.environ.pop("EXTERNAL_DEBUG", None)
    try:
        # Explicit: the var must be genuinely absent for this test to mean
        # anything, not just unset-but-defaulting-the-same-way as "false".
        assert "EXTERNAL_DEBUG" not in os.environ
        assert os.getenv("EXTERNAL_DEBUG") is None
        importlib.reload(config)
        assert config.EXTERNAL_DEBUG is False
        assert hasattr(config, "EXTERNAL_DEBUG")  # attribute exists even when unset
    finally:
        if env_backup is not None:
            os.environ["EXTERNAL_DEBUG"] = env_backup
        importlib.reload(config)


def test_ExternalDebug_EnvVarTrueCaseInsensitive_IsTrue():
    env_backup = os.environ.get("EXTERNAL_DEBUG")
    try:
        os.environ["EXTERNAL_DEBUG"] = "True"
        importlib.reload(config)
        assert config.EXTERNAL_DEBUG is True
    finally:
        if env_backup is None:
            os.environ.pop("EXTERNAL_DEBUG", None)
        else:
            os.environ["EXTERNAL_DEBUG"] = env_backup
        importlib.reload(config)


def test_ExternalDebug_EnvVarGarbageValue_DefaultsFalse():
    env_backup = os.environ.get("EXTERNAL_DEBUG")
    try:
        os.environ["EXTERNAL_DEBUG"] = "yes-please"
        importlib.reload(config)
        assert config.EXTERNAL_DEBUG is False
    finally:
        if env_backup is None:
            os.environ.pop("EXTERNAL_DEBUG", None)
        else:
            os.environ["EXTERNAL_DEBUG"] = env_backup
        importlib.reload(config)
