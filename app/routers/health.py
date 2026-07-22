from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
async def root():
    return {"message": "Welcome to Flame Sport Pheno!"}
