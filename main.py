from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    description: str | None = None

app = FastAPI()

@app.get("/")
def get_root():
    return {"message": "Hello There!"}

@app.post("/items")
def create_item():
    return {"name": "John Doe", "descripion": "Anonymous."}

@app.put("/items")
def change_item():
    return {"name": "Jane Doe", "description": "Also Anonymous."}

@app.patch("/items")
def change_name():
    return {"name": "Mr. Anderson", "description": "An ordinary worker in America"}

@app.delete("/items")
def delete_item():
    return {}