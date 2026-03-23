from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.services.gateway_manager import _manager
from db.schema import DEFAULT_DB_PATH

router = APIRouter()


class GatewayUpdateRequest(BaseModel):
    config: dict[str, str]
    enabled: bool


@router.get("/gateways")
def get_gateways():
    return _manager.get_all(DEFAULT_DB_PATH)


@router.put("/gateways/{name}")
def update_gateway(name: str, req: GatewayUpdateRequest):
    # Check gateway exists in DB
    all_gw = _manager.get_all(DEFAULT_DB_PATH)
    names = [g["name"] for g in all_gw]
    if name not in names:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    _manager.save_config(name, req.config, req.enabled, DEFAULT_DB_PATH)
    updated = _manager.get_all(DEFAULT_DB_PATH)
    return next(g for g in updated if g["name"] == name)


@router.post("/gateways/{name}/connect")
def connect_gateway(name: str):
    try:
        status = _manager.connect(name, DEFAULT_DB_PATH)
        return {"status": status}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/gateways/{name}/disconnect")
def disconnect_gateway(name: str):
    try:
        status = _manager.disconnect(name, DEFAULT_DB_PATH)
        return {"status": status}
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/gateways/{name}/status")
def get_gateway_status(name: str):
    try:
        status = _manager.get_status(name)
        return {"name": name, "status": status}
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail=f"Unknown gateway: {name}")
