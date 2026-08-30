import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker,declarative_base

DATABASE_URL=os.get_env("")

engine=create_engine(DATABASE_URL)
sessionLocal=sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)
Base=declarative_base()
def get_db():
    db=sessionLocal()
    try:
        yield db
    except:
        db.close()
        


