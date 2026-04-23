from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.orm import Session

import app.repository as repo
from app.database import Base, engine, get_db
from app.schemas import TickerCreate, TickerResponse

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ticker Tracker")


@app.get("/tickers", response_model=list[TickerResponse])
def list_tickers(db: Session = Depends(get_db)):
    return repo.get_all(db)


@app.post("/tickers", response_model=TickerResponse, status_code=status.HTTP_201_CREATED)
def add_ticker(payload: TickerCreate, db: Session = Depends(get_db)):
    if repo.get_by_symbol(db, payload.symbol):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{payload.symbol} already exists",
        )
    return repo.create(db, payload.symbol)


@app.delete("/tickers/{symbol}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticker(symbol: str, db: Session = Depends(get_db)):
    ticker = repo.get_by_symbol(db, symbol.upper())
    if not ticker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{symbol.upper()} not found",
        )
    repo.delete(db, ticker)
