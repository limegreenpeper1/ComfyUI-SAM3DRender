"""ComfyUI-SAM3DRender prestartup — ensures the platform-specific
nodes/sam3d/comfy-env.toml exists, then bootstraps comfy-env. The
isolated env (subprocess) is loaded lazily by register_nodes().

NOTE: We deliberately load _env_config via importlib instead of
adding NODE_DIR to sys.path — doing the latter makes our local
``nodes/`` package shadow ComfyUI's top-level ``nodes`` module
(C:\\ComfyUI\\nodes.py), breaking ``nodes.init_extra_nodes``."""

import importlib.util
import os
import sys
from pathlib import Path

NODE_DIR = Path(__file__).resolve().parent
SAM3D_DIR = NODE_DIR / "nodes" / "sam3d"

if sys.platform == "darwin":
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def _load_local(name: str) -> object:
    """Load a sibling .py file by absolute path, no sys.path mutation."""
    spec = importlib.util.spec_from_file_location(name, NODE_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {name} from {NODE_DIR}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _comfy_env_enabled() -> bool:
    return os.environ.get("USE_COMFY_ENV", "1").lower() not in ("0", "false", "no", "off")


def _has_sam3d_env() -> bool:
    if not SAM3D_DIR.is_dir():
        return False
    return any(p.is_dir() and p.name.startswith("_env_") for p in SAM3D_DIR.iterdir())


def _patch_windows_is_junction() -> None:
    # comfy-env 0.1.75 calls Path.is_junction() during the Windows env-move
    # step, but that method only exists in Python 3.12+.
    if sys.platform != "win32" or hasattr(Path, "is_junction"):
        return

    import os as _os

    def _is_junction(self):
        try:
            return bool(_os.readlink(self))
        except (OSError, ValueError):
            return False

    Path.is_junction = _is_junction  # type: ignore[attr-defined]


try:
    _env_config = _load_local("_env_config")
    _env_config.ensure_sam3d_toml(NODE_DIR)
except Exception as _exc:
    print(f"[SAM3DRender] env-config generation failed: {_exc}")

try:
    if _comfy_env_enabled() and not _has_sam3d_env():
        from comfy_env import install

        _patch_windows_is_junction()
        print("[SAM3DRender] SAM3D isolation env missing; running comfy-env install...")
        install(node_dir=NODE_DIR)
except Exception as _exc:
    print(f"[SAM3DRender] comfy-env install failed: {_exc}")

try:
    from comfy_env import setup_env

    setup_env()
except Exception as _exc:
    print(f"[SAM3DRender] comfy-env setup_env failed: {_exc}")
