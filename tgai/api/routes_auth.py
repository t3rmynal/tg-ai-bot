"""Auth routes: credentials, qr login, 2fa, logout."""

from fastapi import APIRouter, Depends, HTTPException

from tgai.api.deps import get_state
from tgai.api.schemas import CredentialsIn, PasswordIn
from tgai.telegram.auth import AuthState

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/status")
async def status(state=Depends(get_state)):
    return state.auth.status()


@router.post("/credentials")
async def set_credentials(body: CredentialsIn, state=Depends(get_state)):
    try:
        await state.auth.set_credentials(body.api_id, body.api_hash)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return state.auth.status()


@router.post("/qr")
async def begin_qr(state=Depends(get_state)):
    try:
        return await state.auth.begin_qr()
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"could not create qr login: {e}") from e


@router.post("/password")
async def submit_password(body: PasswordIn, state=Depends(get_state)):
    if state.auth.state != AuthState.PASSWORD_NEEDED:
        raise HTTPException(status_code=409, detail="no password prompt pending")
    try:
        await state.auth.submit_password(body.password)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e
    return state.auth.status()


@router.post("/logout")
async def logout(state=Depends(get_state)):
    await state.auth.logout()
    return {"ok": True}
